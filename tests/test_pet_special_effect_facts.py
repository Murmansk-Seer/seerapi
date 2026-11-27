from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from solaris.analyze.output import pet_special_effect_resolution as resolution
from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(':memory:')
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
        CREATE TABLE special_effect_status_variant (
            status_id INTEGER NOT NULL,
            variant_value INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon_key TEXT NOT NULL
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


def test_link_sources_preserve_shared_child_and_direct_evidence() -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (9000, 'Test pet')")
    connection.executemany(
        'INSERT INTO glossary_entry VALUES (?, ?, ?)',
        [(10, 'Parent A', 'A'), (20, 'Parent B', 'B'), (30, 'Child', 'C')],
    )
    connection.executemany(
        'INSERT INTO petglossaryentrylink VALUES (9000, ?)',
        [(10,), (20,), (30,)],
    )
    connection.executemany(
        'INSERT INTO glossaryentrylink VALUES (?, ?)',
        [(10, 30), (20, 30), (10, 30), (30, 10), (30, 30)],
    )

    for now in (1.0, 2.0):
        replace_pet_special_effect_facts(connection, now=now)
        assert connection.execute(
            'SELECT effect_key, primary_rule FROM pet_special_effect '
            'ORDER BY effect_key'
        ).fetchall() == [
            ('g:10', 'direct_pet_glossary'),
            ('g:20', 'direct_pet_glossary'),
            ('g:30', 'direct_pet_glossary'),
        ]
        assert connection.execute(
            'SELECT effect_key, source_id FROM pet_special_effect_source '
            "WHERE source_kind = 'glossary_link' ORDER BY effect_key, source_id"
        ).fetchall() == [('g:10', 30), ('g:30', 10), ('g:30', 20)]
        assert connection.execute(
            'SELECT source_kind, source_id FROM pet_special_effect_source '
            "WHERE effect_key = 'g:30' ORDER BY source_kind, source_id"
        ).fetchall() == [
            ('glossary_link', 10),
            ('glossary_link', 20),
            ('pet_glossary', 30),
        ]


@pytest.mark.parametrize('linked', [False, True])
def test_duplicate_effect_names_use_direct_glossary_or_record_ambiguity(
    linked: bool,
) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (4525, '二郎神')")
    candidates = [
        (223, '法天象地', '孙悟空必定致命一击'),
        (224, '法天象地', '二郎神吸取300体力'),
    ]
    connection.executemany('INSERT INTO glossary_entry VALUES (?, ?, ?)', candidates)
    connection.executemany(
        'INSERT INTO effect_description VALUES (?, ?, ?)', candidates
    )
    if linked:
        connection.execute('INSERT INTO petglossaryentrylink VALUES (4525, 224)')
    for soulmark_id, description in [
        (1739, '触发法天象地'),
        (1939, '升级后触发法天象地'),
    ]:
        connection.execute(
            "INSERT INTO soulmark VALUES (?, ?, '', '', 0, 0, NULL)",
            (soulmark_id, description),
        )
        connection.execute(
            'INSERT INTO petsoulmarklink VALUES (4525, ?)', (soulmark_id,)
        )
    replace_pet_special_effect_facts(connection, now=1)
    rows = connection.execute(
        'SELECT glossary_id FROM pet_special_effect WHERE pet_id=4525'
    ).fetchall()
    assert rows == ([(224,)] if linked else [])
    issues = connection.execute(
        "SELECT candidate_id, context FROM pet_special_effect_issue WHERE reason IN ('ambiguous_text_effect_name', 'unverified_text_ownership') ORDER BY candidate_id"
    ).fetchall()
    if linked:
        assert not issues
        sources = connection.execute(
            "SELECT source_id FROM pet_special_effect_source WHERE source_kind='soulmark' ORDER BY source_id"
        ).fetchall()
        assert sources == []
    else:
        assert [row[0] for row in issues] == [223, 224]
        assert all(
            '触发法天象地' in row[1] and '升级后触发法天象地' in row[1]
            for row in issues
        )


@pytest.mark.parametrize('explicit', [False, True])
def test_skill_reference_considers_later_duplicate_description(explicit: bool) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1, 'test')")
    description = '使用技能「吸取」后触发效果' if explicit else '吸取对手300点体力'
    candidates = [(10, '同名', '其他技能'), (11, '同名', description)]
    connection.executemany('INSERT INTO glossary_entry VALUES (?, ?, ?)', candidates)
    connection.executemany(
        'INSERT INTO effect_description VALUES (?, ?, ?)', candidates
    )
    connection.execute("INSERT INTO skill VALUES (100, '吸取', '造成伤害', NULL)")
    connection.execute('INSERT INTO skillinpetorm VALUES (1, 100)')
    replace_pet_special_effect_facts(connection, now=1)
    assert (
        connection.execute('SELECT glossary_id FROM pet_special_effect').fetchall()
        == []
    )
    assert connection.execute(
        'SELECT COUNT(*) FROM pet_special_effect_issue'
    ).fetchone()[0] == (2 if explicit else 0)


@pytest.mark.parametrize(
    ('descriptions', 'context', 'expected'),
    [
        (('必定致命一击', '吸取300点体力'), '同名：吸取300点体力', []),
        (('相同描述', '相同描述'), '触发同名', []),
        (('...', '吸取300点体力'), '触发同名', []),
    ],
)
def test_duplicate_text_candidates_do_not_use_description_evidence(
    descriptions: tuple[str, str], context: str, expected: list[int]
) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1, 'test')")
    candidates = [(10 + i, '同名', text) for i, text in enumerate(descriptions)]
    connection.executemany('INSERT INTO glossary_entry VALUES (?, ?, ?)', candidates)
    connection.executemany(
        'INSERT INTO effect_description VALUES (?, ?, ?)', candidates
    )
    connection.execute(
        "INSERT INTO soulmark VALUES (1, ?, '', '', 0, 0, NULL)",
        (context.replace('同名', '[color=#f35555]同名[/color]'),),
    )
    connection.execute('INSERT INTO petsoulmarklink VALUES (1, 1)')
    replace_pet_special_effect_facts(connection, now=1)
    assert [
        row[0]
        for row in connection.execute('SELECT glossary_id FROM pet_special_effect')
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
    connection.executemany('INSERT INTO skillinpetorm VALUES (?, 100)', [(1,), (2,)])
    original = resolution._skill_description_references
    calls: list[str] = []

    def scan(name, descriptions):
        calls.append(name)
        return original(name, descriptions)

    monkeypatch.setattr(resolution, '_skill_description_references', scan)
    replace_pet_special_effect_facts(connection, now=1)
    assert calls == ['吸取']
    assert connection.execute('SELECT pet_id FROM pet_special_effect').fetchall() == []
    assert connection.execute(
        'SELECT COUNT(*) FROM pet_special_effect_issue'
    ).fetchone() == (2,)

    connection.execute("UPDATE effect_description SET description='吸取对手300点体力'")
    replace_pet_special_effect_facts(connection, now=2)
    assert calls == ['吸取', '吸取']
    assert connection.execute('SELECT COUNT(*) FROM pet_special_effect').fetchone() == (
        0,
    )
    assert connection.execute(
        'SELECT COUNT(*) FROM pet_special_effect_issue'
    ).fetchone() == (0,)


def test_builds_linked_effect_facts_with_source_provenance() -> None:
    connection = _connection()
    connection.executemany(
        'INSERT INTO pet (id, name) VALUES (?, ?)',
        [(3549, '灵天圣君·萨尔蒙'), (4911, '星光·艾欧丽娅')],
    )
    connection.executemany(
        'INSERT INTO glossary_entry (id, name, desc) VALUES (?, ?, ?)',
        [
            (533, '四象门', '转化为六芒阵'),
            (534, '六芒阵', '升阶为八方圻'),
            (535, '八方圻', '最终效果'),
            (600, '骑士决斗·落败', '无法行动'),
        ],
    )
    connection.executemany(
        'INSERT INTO effect_description (effect_id, name, description) VALUES (?, ?, ?)',
        [(533, '四象门', '转化为六芒阵')],
    )
    connection.executemany(
        'INSERT INTO glossaryentrylink (source_id, target_id) VALUES (533, ?)',
        [(534,), (535,)],
    )
    connection.execute(
        "INSERT INTO skill (id, name, info) VALUES (100, '繁苍解道', '[color=#f35555]四象门[/color]')"
    )
    connection.execute('INSERT INTO skillinpetorm VALUES (3549, 100)')
    connection.execute('INSERT INTO petglossaryentrylink VALUES (4911, 600)')
    connection.executemany(
        """
        INSERT INTO special_effect_status
            (status_id, name, description, show_monster_id)
        VALUES (?, ?, ?, ?)
        """,
        [
            (188, '四象门', '转化为六芒阵', 0),
            (183, '骑士决斗·落败', '无法行动', 0),
            (184, '骑士决斗·落败', '无法行动', 0),
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
        'INSERT INTO petsoulmarklink VALUES (3549, ?)',
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
        (533, '四象门', None),
        (534, '六芒阵', None),
        (535, '八方圻', None),
    ]
    assert ('skill', 100, 'skill_highlight_exact') in salmon_sources
    assert knight == (600, None)
    assert soulmark_order == [(1, 1, 0, 'base'), (2, 1, 1, 'intensified')]


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
            '登场首回合所有攻击先制+1同时增加20%暴击率',
            1,
            0,
            None,
            '[]',
            0,
            'seerapi/soulmark-display-corrections#pet-2500-v1',
        )
    ]


def test_named_status_variants_do_not_bridge_unrelated_glossary_ids() -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (3488, '阴灵魂姬')")
    connection.executemany(
        'INSERT INTO glossary_entry VALUES (?, ?, ?)',
        [(544, '冥妖之悼', '第一条说明'), (545, '幽迹之秘', '第二条说明')],
    )
    connection.executemany(
        'INSERT INTO effect_description VALUES (?, ?, ?)',
        [(544, '冥妖之悼', '第一条说明'), (545, '幽迹之秘', '第二条说明')],
    )
    connection.execute(
        'INSERT INTO skill (id, name, info) VALUES '
        "(29402, '黄泉妖偈', '获得[color=#f35555]冥妖之悼[/color]或[color=#f35555]幽迹之秘[/color]')"
    )
    connection.execute('INSERT INTO skillinpetorm VALUES (3488, 29402)')
    connection.execute(
        "INSERT INTO special_effect_status VALUES (191, '阴冥之择', '', 0)"
    )
    connection.executemany(
        'INSERT INTO special_effect_status_variant VALUES (?, ?, ?, ?, ?)',
        [
            (191, 1, '冥妖之悼', '第一条说明', '191_1'),
            (191, 2, '幽迹之秘', '第二条说明', '191_2'),
        ],
    )

    replace_pet_special_effect_facts(connection, now=1.0)

    assert connection.execute(
        'SELECT name, icon_key FROM pet_special_effect '
        'WHERE pet_id=3488 ORDER BY glossary_id'
    ).fetchall() == [('冥妖之悼', None), ('幽迹之秘', None)]

    replace_pet_special_effect_facts(
        connection, now=2.0, available_icon_keys=frozenset({'191_1'})
    )
    assert connection.execute(
        'SELECT name, icon_key FROM pet_special_effect '
        'WHERE pet_id=3488 ORDER BY glossary_id'
    ).fetchall() == [('冥妖之悼', None), ('幽迹之秘', None)]


@pytest.mark.parametrize(
    ('description', 'expected_icon'),
    [('对应说明', None), ('不相同的说明', None)],
)
def test_ambiguous_variant_name_is_not_resolved_by_description(
    description: str,
    expected_icon: str | None,
) -> None:
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (9000, '测试精灵')")
    connection.execute(
        'INSERT INTO glossary_entry VALUES (77, ?, ?)', ('重名效果', description)
    )
    connection.execute(
        'INSERT INTO effect_description VALUES (77, ?, ?)',
        ('重名效果', description),
    )
    connection.execute('INSERT INTO petglossaryentrylink VALUES (9000, 77)')
    connection.executemany(
        'INSERT INTO special_effect_status_variant VALUES (?, ?, ?, ?, ?)',
        [
            (10, 1, '重名效果', '对应说明', '10_1'),
            (11, 2, '重名效果', '另一分支说明', '11_2'),
        ],
    )

    replace_pet_special_effect_facts(connection, now=1.0)

    assert connection.execute(
        'SELECT icon_key FROM pet_special_effect WHERE pet_id=9000'
    ).fetchone() == (expected_icon,)
    assert connection.execute(
        'SELECT COUNT(*) FROM pet_special_effect_issue '
        "WHERE reason='ambiguous_variant_icon'"
    ).fetchone() == (0,)


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
        [(10, '基础魂印'), (20, '强化魂印')],
    )
    connection.executemany(
        'INSERT INTO petsoulmarklink (pet_id, soulmark_id) VALUES (7000, ?)',
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

    assert rows == [(10, 'base'), (20, 'partner_upgrade')]


@pytest.mark.parametrize(
    ('name', 'text'),
    [
        ('幕', '集结天幕龙神之力'),
        ('龙神之力', '集结天幕龙神之力'),
        ('失体', '附加已损失体力值30%的百分比伤害'),
        ('刻', '在灵魂深处刻下了印记'),
        ('烛', '如风中残烛'),
        ('辛', '辛克斯善于蛊惑心智'),
        ('回能', '下回能更快的出手了'),
        ('龙胆', '龙胆天神恢复150点体力'),
        ('群辉加护', '自身出战时获得群辉加护'),
        ('未来指令', '未来链接同时也视为未来奇点、未来指令参与结算'),
    ],
)
@pytest.mark.parametrize('kind', ['skill', 'soulmark'])
def test_plain_mentions_do_not_create_ownership_or_linked_children(name, text, kind):
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1, 'test')")
    connection.executemany(
        'INSERT INTO glossary_entry VALUES (?, ?, ?)',
        [(10, name, 'effect'), (11, 'Child', 'child effect')],
    )
    connection.execute(
        'INSERT INTO effect_description VALUES (10, ?, ?)', (name, 'effect')
    )
    connection.execute('INSERT INTO glossaryentrylink VALUES (10, 11)')
    connection.execute(
        'INSERT INTO special_effect_status VALUES (5, ?, ?, 0)', (name, 'effect')
    )
    if kind == 'skill':
        connection.execute("INSERT INTO skill VALUES (100, 'test', ?, NULL)", (text,))
        connection.execute('INSERT INTO skillinpetorm VALUES (1, 100)')
    else:
        connection.execute(
            "INSERT INTO soulmark VALUES (100, ?, '', '', 0, 0, NULL)", (text,)
        )
        connection.execute('INSERT INTO petsoulmarklink VALUES (1, 100)')
    for now in (1, 2):
        replace_pet_special_effect_facts(connection, now=now)
        assert connection.execute(
            'SELECT COUNT(*) FROM pet_special_effect'
        ).fetchone() == (0,)
        assert connection.execute(
            'SELECT COUNT(*) FROM pet_special_effect_source'
        ).fetchone() == (0,)
        issue = connection.execute(
            'SELECT reason,context FROM pet_special_effect_issue'
        ).fetchone()
        assert issue == ('unverified_text_ownership', text)


@pytest.mark.parametrize(
    ('text', 'ids'),
    [
        ('[color=#f35555]幕[/color]', [10, 11]),
        ('[color=#f35555]幕(10)[/color]', [10, 11]),
        ('[color=#f35555]幕(999)[/color]', []),
        ('[color=#f35555]天幕[/color]', []),
        ('[color=#f35555]幕A[/color]', []),
        ('[color=#f35555]幕Child[/color]', []),
        ('[color=#f35555]幕、Child[/color]', [10, 11]),
        ('[color=#f35555]幕', []),
        ('[color=#f35555][color=#52a5f2]幕[/color]天幕', [10, 11]),
    ],
)
def test_whole_marked_names_ids_and_official_batch_color_closing(text, ids):
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1, 'test')")
    connection.executemany(
        'INSERT INTO glossary_entry VALUES (?, ?, ?)',
        [(10, '幕', 'effect'), (11, 'Child', 'child')],
    )
    connection.executemany(
        'INSERT INTO effect_description VALUES (?, ?, ?)',
        [(10, '幕', 'effect'), (11, 'Child', 'child')],
    )
    connection.execute('INSERT INTO glossaryentrylink VALUES (10, 11)')
    connection.execute("INSERT INTO skill VALUES (100, 'test', ?, NULL)", (text,))
    connection.execute('INSERT INTO skillinpetorm VALUES (1, 100)')
    replace_pet_special_effect_facts(connection, now=1)
    assert [
        row[0]
        for row in connection.execute(
            'SELECT glossary_id FROM pet_special_effect ORDER BY glossary_id'
        )
    ] == ids
    if '(999)' in text:
        assert connection.execute(
            "SELECT COUNT(*) FROM pet_special_effect_issue WHERE reason='invalid_marked_effect_reference'"
        ).fetchone() == (1,)


def test_official_single_character_relation_survives_plain_false_positive():
    connection = _connection()
    connection.executemany(
        'INSERT INTO pet VALUES (?, ?)', [(1, 'Owner'), (2, 'Other')]
    )
    connection.execute("INSERT INTO glossary_entry VALUES (10, '幕', 'effect')")
    connection.execute("INSERT INTO effect_description VALUES (10, '幕', 'effect')")
    connection.execute('INSERT INTO petglossaryentrylink VALUES (1, 10)')
    connection.execute("INSERT INTO skill VALUES (100, 'test', '天幕', NULL)")
    connection.executemany('INSERT INTO skillinpetorm VALUES (?, 100)', [(1,), (2,)])
    replace_pet_special_effect_facts(connection, now=1)
    assert connection.execute(
        'SELECT pet_id,glossary_id FROM pet_special_effect'
    ).fetchall() == [(1, 10)]
    assert (
        connection.execute(
            "SELECT pet_id FROM pet_special_effect_source WHERE source_kind='skill'"
        ).fetchall()
        == []
    )


def test_frozen_release_ownership_and_raw_business_data_are_preserved():
    fixture = json.loads(
        (
            Path(__file__).parent / 'fixtures/pet-effect-ownership-20261121.json'
        ).read_text('utf8')
    )
    assert (
        fixture['source_sha256']
        == '78b2a2f0f5f009db74a1efffb006695dca8a3dfb6e439249c08cd11a6792c6c0'
    )
    connection = _connection()
    for table, data in fixture['tables'].items():
        columns = ','.join(f'"{name}"' for name in data['columns'])
        placeholders = ','.join('?' for _ in data['columns'])
        connection.executemany(
            f'INSERT INTO "{table}" ({columns}) VALUES ({placeholders})', data['rows']
        )
    business = {
        table: connection.execute(f'SELECT * FROM "{table}"').fetchall()
        for table in fixture['tables']
    }
    original_direct = set(
        connection.execute('SELECT pet_id,glossary_entry_id FROM petglossaryentrylink')
    )
    for now in (1, 2):
        replace_pet_special_effect_facts(connection, now=now)
        actual = set(
            connection.execute('SELECT pet_id,glossary_id FROM pet_special_effect')
        )
        assert original_direct <= actual
        assert {id_ for pet, id_ in actual if pet == 4012} == {51, 52, 53, 54}
        assert (3809, 72) in actual
        assert {(4861, id_) for id_ in range(420, 427)} <= actual
        for pet, name in (
            (4364, '群辉加护'),
            (4364, '群芳加护'),
            (4950, '星皇之赐'),
            (4950, '星皇之佑'),
            (4956, '谋死'),
        ):
            assert connection.execute(
                'SELECT 1 FROM pet_special_effect WHERE pet_id=? AND name=?',
                (pet, name),
            ).fetchone()
        for name in ('未来奇点', '未来指令'):
            assert not connection.execute(
                'SELECT 1 FROM pet_special_effect WHERE pet_id=4600 AND name=?', (name,)
            ).fetchone()
            assert connection.execute(
                "SELECT 1 FROM pet_special_effect_issue WHERE pet_id=4600 AND effect_name=? AND reason='unverified_text_ownership'",
                (name,),
            ).fetchone()
        assert not connection.execute(
            "SELECT 1 FROM pet_special_effect_source WHERE resolution_rule IN ('text_exact_name','effect_description_skill_name')"
        ).fetchone()
        for table, expected in business.items():
            assert connection.execute(f'SELECT * FROM "{table}"').fetchall() == expected


def test_marked_id_disambiguates_identical_names_without_guessing():
    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1,'test')")
    candidates = [(10, '同名', 'A'), (11, '同名', 'B')]
    connection.executemany('INSERT INTO glossary_entry VALUES (?,?,?)', candidates)
    connection.executemany('INSERT INTO effect_description VALUES (?,?,?)', candidates)
    connection.execute(
        "INSERT INTO skill VALUES (100,'test','[color=#f35555]同名(11)[/color]',NULL)"
    )
    connection.execute('INSERT INTO skillinpetorm VALUES (1,100)')
    replace_pet_special_effect_facts(connection, now=1)
    assert connection.execute(
        'SELECT glossary_id FROM pet_special_effect'
    ).fetchall() == [(11,)]


def test_audit_uses_fresh_copy_and_keeps_source_bytes(tmp_path):
    from hashlib import sha256

    from scripts.audit_pet_special_effect_ownership import audit

    connection = _connection()
    connection.execute("INSERT INTO pet VALUES (1,'test')")
    connection.executemany(
        'INSERT INTO glossary_entry VALUES (?,?,?)',
        [(10, '幕', 'A'), (11, 'Real', 'B')],
    )
    connection.execute('INSERT INTO petglossaryentrylink VALUES (1,11)')
    connection.execute("INSERT INTO effect_description VALUES (10,'幕','A')")
    connection.execute("INSERT INTO skill VALUES (100,'test','天幕',NULL)")
    connection.execute('INSERT INTO skillinpetorm VALUES (1,100)')
    replace_pet_special_effect_facts(connection, now=0)
    connection.execute(
        "INSERT INTO pet_special_effect (pet_id,effect_key,glossary_id,status_id,icon_key,name,description,sort_id,sort_kind,primary_rule,updated_at) VALUES (1,'g:10',10,NULL,NULL,'幕','A',10,'glossary','text_exact_name',0)"
    )
    connection.execute(
        "INSERT INTO pet_special_effect_source VALUES (1,'g:10','skill',100,'text_exact_name','test',0)"
    )
    connection.commit()
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(source) as target:
        connection.backup(target)
    digest = sha256(source.read_bytes()).hexdigest()
    report = audit(source, tmp_path / 'audit')
    assert report['source_sha256'] == digest
    assert report['weak_count'] == report['removed_count'] == 1
    assert report['after_count'] == 1
    assert sha256(source.read_bytes()).hexdigest() == digest
    assert (tmp_path / 'audit/audit.md').is_file()
    with pytest.raises(FileExistsError):
        audit(source, tmp_path / 'audit')
