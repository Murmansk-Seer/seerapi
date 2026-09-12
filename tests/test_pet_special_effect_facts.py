from __future__ import annotations

import sqlite3

import pytest

from solaris.analyze.output import pet_special_effect_resolution as resolution
from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE pet (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE glossary_entry (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            desc TEXT NOT NULL
        );
        CREATE TABLE petglossaryentrylink (
            pet_id INTEGER NOT NULL,
            glossary_entry_id INTEGER NOT NULL
        );
        CREATE TABLE glossaryentrylink (
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL
        );
        CREATE TABLE special_effect_status (
            status_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            show_monster_id INTEGER NOT NULL
        );
        CREATE TABLE effect_description (
            effect_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL
        );
        CREATE TABLE skill (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            info TEXT,
            hide_effect_id INTEGER
        );
        CREATE TABLE skillinpetorm (
            pet_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL
        );
        CREATE TABLE skill_effect_in_use (
            id INTEGER PRIMARY KEY,
            info TEXT,
            analyze_info TEXT
        );
        CREATE TABLE skilleffectlink (
            skill_id INTEGER NOT NULL,
            effect_in_use_id INTEGER NOT NULL
        );
        CREATE TABLE skillfriendskilleffectlink (
            skill_id INTEGER NOT NULL,
            effect_in_use_id INTEGER NOT NULL
        );
        CREATE TABLE skill_hide_effect (
            id INTEGER PRIMARY KEY,
            description TEXT
        );
        CREATE TABLE soulmark (
            id INTEGER PRIMARY KEY,
            desc TEXT,
            analyze_desc TEXT,
            desc_formatting_adjustment TEXT,
            intensified INTEGER NOT NULL,
            is_adv INTEGER NOT NULL,
            intensified_to_id INTEGER
        );
        CREATE TABLE petsoulmarklink (
            pet_id INTEGER NOT NULL,
            soulmark_id INTEGER NOT NULL
        );
        CREATE TABLE pet_partner_upgrade (
            pet_id INTEGER PRIMARY KEY,
            before_description TEXT NOT NULL,
            after_description TEXT NOT NULL
        );
        """
    )
    return connection


@pytest.mark.parametrize("linked", [False, True])
def test_duplicate_effect_names_use_direct_glossary_or_record_ambiguity(
    linked: bool,
) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (4525, '二郎神')")
    candidates = [
        (223, "法天象地", "孙悟空必定致命一击"),
        (224, "法天象地", "二郎神吸取300体力"),
    ]
    connection.executemany("INSERT INTO glossary_entry VALUES (?, ?, ?)", candidates)
    connection.executemany(
        "INSERT INTO effect_description VALUES (?, ?, ?)", candidates
    )
    if linked:
        connection.execute("INSERT INTO petglossaryentrylink VALUES (4525, 224)")
    for soulmark_id, description in [
        (1739, "触发法天象地"),
        (1939, "升级后触发法天象地"),
    ]:
        connection.execute(
            "INSERT INTO soulmark VALUES (?, ?, '', '', 0, 0, NULL)",
            (soulmark_id, description),
        )
        connection.execute(
            "INSERT INTO petsoulmarklink VALUES (4525, ?)", (soulmark_id,)
        )
    replace_pet_special_effect_facts(connection, now=1)
    rows = connection.execute(
        "SELECT glossary_id FROM pet_special_effect WHERE pet_id=4525"
    ).fetchall()
    assert rows == ([(224,)] if linked else [])
    issues = connection.execute(
        "SELECT candidate_id, context FROM pet_special_effect_issue WHERE reason='ambiguous_text_effect_name' ORDER BY candidate_id"
    ).fetchall()
    if linked:
        assert not issues
        sources = connection.execute(
            "SELECT source_id FROM pet_special_effect_source WHERE source_kind='soulmark' ORDER BY source_id"
        ).fetchall()
        assert sources == [(1739,), (1939,)]
    else:
        assert [row[0] for row in issues] == [223, 224]
        assert all(
            "触发法天象地" in row[1] and "升级后触发法天象地" in row[1]
            for row in issues
        )


@pytest.mark.parametrize("explicit", [False, True])
def test_skill_reference_considers_later_duplicate_description(explicit: bool) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1, 'test')")
    description = "使用技能「吸取」后触发效果" if explicit else "吸取对手300点体力"
    candidates = [(10, "同名", "其他技能"), (11, "同名", description)]
    connection.executemany("INSERT INTO glossary_entry VALUES (?, ?, ?)", candidates)
    connection.executemany(
        "INSERT INTO effect_description VALUES (?, ?, ?)", candidates
    )
    connection.execute("INSERT INTO skill VALUES (100, '吸取', '造成伤害', NULL)")
    connection.execute("INSERT INTO skillinpetorm VALUES (1, 100)")
    replace_pet_special_effect_facts(connection, now=1)
    assert connection.execute(
        "SELECT glossary_id FROM pet_special_effect"
    ).fetchall() == ([(11,)] if explicit else [])


@pytest.mark.parametrize(
    ("descriptions", "context", "expected"),
    [
        (("必定致命一击", "吸取300点体力"), "同名：吸取300点体力", [11]),
        (("相同描述", "相同描述"), "触发同名", [10]),
        (("...", "吸取300点体力"), "触发同名", []),
    ],
)
def test_duplicate_text_candidates_require_description_evidence(
    descriptions: tuple[str, str], context: str, expected: list[int]
) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1, 'test')")
    candidates = [(10 + i, "同名", text) for i, text in enumerate(descriptions)]
    connection.executemany("INSERT INTO glossary_entry VALUES (?, ?, ?)", candidates)
    connection.executemany(
        "INSERT INTO effect_description VALUES (?, ?, ?)", candidates
    )
    connection.execute(
        "INSERT INTO soulmark VALUES (1, ?, '', '', 0, 0, NULL)", (context,)
    )
    connection.execute("INSERT INTO petsoulmarklink VALUES (1, 1)")
    replace_pet_special_effect_facts(connection, now=1)
    assert [
        row[0]
        for row in connection.execute("SELECT glossary_id FROM pet_special_effect")
    ] == expected


def test_skill_reference_scan_is_shared_only_within_one_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = _connection()
    connection.executemany("INSERT INTO pet VALUES (?, 'test')", [(1,), (2,)])
    connection.execute(
        "INSERT INTO glossary_entry VALUES (10, '同名', '技能「吸取」触发')"
    )
    connection.execute(
        "INSERT INTO effect_description VALUES (10, '同名', '技能「吸取」触发')"
    )
    connection.execute("INSERT INTO skill VALUES (100, '吸取', '造成伤害', NULL)")
    connection.executemany("INSERT INTO skillinpetorm VALUES (?, 100)", [(1,), (2,)])
    original = resolution._skill_description_references
    calls: list[str] = []

    def scan(name, descriptions):
        calls.append(name)
        return original(name, descriptions)

    monkeypatch.setattr(resolution, "_skill_description_references", scan)
    replace_pet_special_effect_facts(connection, now=1)
    assert calls == ["吸取"]
    assert connection.execute(
        "SELECT pet_id FROM pet_special_effect ORDER BY pet_id"
    ).fetchall() == [(1,), (2,)]

    connection.execute("UPDATE effect_description SET description='吸取对手300点体力'")
    replace_pet_special_effect_facts(connection, now=2)
    assert calls == ["吸取", "吸取"]
    assert connection.execute("SELECT COUNT(*) FROM pet_special_effect").fetchone() == (
        0,
    )


def test_builds_linked_effect_facts_with_source_provenance() -> None:
    connection = _connection()
    connection.executemany(
        "INSERT INTO pet (id, name) VALUES (?, ?)",
        [(3549, "灵天圣君·萨尔蒙"), (4911, "星光·艾欧丽娅")],
    )
    connection.executemany(
        "INSERT INTO glossary_entry (id, name, desc) VALUES (?, ?, ?)",
        [
            (533, "四象门", "转化为六芒阵"),
            (534, "六芒阵", "升阶为八方圻"),
            (535, "八方圻", "最终效果"),
            (600, "骑士决斗·落败", "无法行动"),
        ],
    )
    connection.executemany(
        "INSERT INTO effect_description (effect_id, name, description) VALUES (?, ?, ?)",
        [(533, "四象门", "转化为六芒阵")],
    )
    connection.executemany(
        "INSERT INTO glossaryentrylink (source_id, target_id) VALUES (533, ?)",
        [(534,), (535,)],
    )
    connection.execute(
        "INSERT INTO skill (id, name, info) VALUES (100, '繁苍解道', '[color=#f35555]四象门[/color]')"
    )
    connection.execute("INSERT INTO skillinpetorm VALUES (3549, 100)")
    connection.execute("INSERT INTO petglossaryentrylink VALUES (4911, 600)")
    connection.executemany(
        """
        INSERT INTO special_effect_status
            (status_id, name, description, show_monster_id)
        VALUES (?, ?, ?, ?)
        """,
        [
            (188, "四象门", "转化为六芒阵", 0),
            (183, "骑士决斗·落败", "无法行动", 0),
            (184, "骑士决斗·落败", "无法行动", 0),
        ],
    )
    connection.executemany(
        """
        INSERT INTO soulmark
            (id, desc, analyze_desc, desc_formatting_adjustment, intensified, is_adv, intensified_to_id)
        VALUES (?, '', '', '', ?, ?, ?)
        """,
        [(1, 0, 0, 2), (2, 1, 0, None)],
    )
    connection.executemany(
        "INSERT INTO petsoulmarklink VALUES (3549, ?)",
        [(1,), (2,)],
    )

    summary = replace_pet_special_effect_facts(connection, now=1.0)

    salmon_effects = connection.execute(
        """
        SELECT glossary_id, name, status_id
        FROM pet_special_effect
        WHERE pet_id = 3549
        ORDER BY sort_id
        """
    ).fetchall()
    salmon_sources = connection.execute(
        """
        SELECT source_kind, source_id, resolution_rule
        FROM pet_special_effect_source
        WHERE pet_id = 3549 AND effect_key = 'g:533'
        ORDER BY source_kind, source_id, resolution_rule
        """
    ).fetchall()
    knight = connection.execute(
        """
        SELECT glossary_id, status_id
        FROM pet_special_effect
        WHERE pet_id = 4911
        """
    ).fetchone()
    soulmark_order = connection.execute(
        """
        SELECT soulmark_id, root_soulmark_id, display_order, display_kind
        FROM pet_soulmark_display
        WHERE pet_id = 3549
        ORDER BY display_order
        """
    ).fetchall()

    assert summary.facts == 4
    assert summary.soulmark_display_rows == 2
    assert summary.soulmark_display_addition_rows == 1
    assert salmon_effects == [
        (533, "四象门", 188),
        (534, "六芒阵", None),
        (535, "八方圻", None),
    ]
    assert ("skill", 100, "skill_highlight_exact") in salmon_sources
    assert knight == (600, 183)
    assert soulmark_order == [(1, 1, 0, "base"), (2, 1, 1, "intensified")]


def test_publishes_declared_soulmark_display_additions() -> None:
    connection = _connection()

    replace_pet_special_effect_facts(connection, now=1.0)

    rows = connection.execute(
        """
        SELECT pet_id, display_id, description, intensified, is_adv,
               pve_effective, tags_json, display_order, source
        FROM pet_soulmark_display_addition
        """
    ).fetchall()

    assert rows == [
        (
            2500,
            0,
            "登场首回合所有攻击先制+1同时增加20%暴击率",
            1,
            0,
            None,
            "[]",
            0,
            "seerapi/soulmark-display-corrections#pet-2500-v1",
        )
    ]


def test_publishes_partner_upgrade_soulmark_display_kind() -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet (id, name) VALUES (7000, '测试精灵')")
    connection.executemany(
        """
        INSERT INTO soulmark
            (
                id, desc, analyze_desc, desc_formatting_adjustment, intensified,
                is_adv, intensified_to_id
            )
        VALUES (?, ?, NULL, NULL, 0, 0, NULL)
        """,
        [(10, "基础魂印"), (20, "强化魂印")],
    )
    connection.executemany(
        "INSERT INTO petsoulmarklink (pet_id, soulmark_id) VALUES (7000, ?)",
        [(10,), (20,)],
    )
    connection.execute(
        """
        INSERT INTO pet_partner_upgrade
            (pet_id, before_description, after_description)
        VALUES (7000, '基础魂印', '强化魂印')
        """
    )

    replace_pet_special_effect_facts(connection, now=1.0)

    rows = connection.execute(
        """
        SELECT soulmark_id, display_kind
        FROM pet_soulmark_display
        WHERE pet_id = 7000
        ORDER BY display_order
        """
    ).fetchall()

    assert rows == [(10, "base"), (20, "partner_upgrade")]
