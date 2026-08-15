import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / 'scripts' / 'build_new_content_index.py'
)
SPEC = importlib.util.spec_from_file_location('build_new_content_index', SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
indexer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = indexer
SPEC.loader.exec_module(indexer)


def _create_database(path: Path, *, version: str, pet_ids: tuple[int, ...]) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE ironsbot_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE achievement (
                id INTEGER PRIMARY KEY, name TEXT, point INTEGER, desc TEXT, is_hide INTEGER
            );
            CREATE TABLE title_part (
                id INTEGER PRIMARY KEY, name TEXT, original_name TEXT,
                ability_desc TEXT, achievement_id INTEGER
            );
            CREATE TABLE peak_pool (
                id INTEGER PRIMARY KEY, count INTEGER NOT NULL,
                start_time TEXT NOT NULL, end_time TEXT NOT NULL
            );
            CREATE TABLE pet (
                id INTEGER PRIMARY KEY, name TEXT,
                peak_pool_id INTEGER, peak_expert_pool_id INTEGER
            );
            CREATE TABLE skill (id INTEGER PRIMARY KEY, name TEXT, info TEXT);
            CREATE TABLE pet_skin (
                id INTEGER PRIMARY KEY, name TEXT, resource_id INTEGER, pet_id INTEGER
            );
            CREATE TABLE mintmark (id INTEGER PRIMARY KEY, name TEXT, desc TEXT);
            CREATE TABLE mintmark_quality (
                mintmark_id INTEGER PRIMARY KEY,
                quality INTEGER NOT NULL
            );
            CREATE TABLE suit (id INTEGER PRIMARY KEY, name TEXT, suit_desc TEXT);
            CREATE TABLE equip (
                id INTEGER PRIMARY KEY, name TEXT, part_type_id INTEGER, suit_id INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO ironsbot_metadata (key, value) VALUES ('config_package_version', ?)",
            (version,),
        )
        conn.execute(
            "INSERT INTO achievement VALUES (6086031, '不动明王护法', 0, '礼包获得', 0)"
        )
        conn.execute(
            "INSERT INTO title_part VALUES (177, '不动明王护法', '', '', 6086031)"
        )
        conn.executemany(
            'INSERT INTO pet VALUES (?, ?, NULL, NULL)',
            [(item, f'精灵{item}') for item in pet_ids],
        )
        conn.executemany(
            'INSERT INTO peak_pool VALUES (?, ?, ?, ?)',
            (
                (0, 0, '2026-07-17 10:00:00', '2026-08-14 10:00:00'),
                (2, 2, '2026-07-17 10:00:00', '2026-08-14 10:00:00'),
                (3, 3, '2026-07-17 10:00:00', '2026-08-14 10:00:00'),
            ),
        )
        conn.execute("INSERT INTO skill VALUES (9000, '基础技能', '基础效果')")
        conn.execute("INSERT INTO pet_skin VALUES (100, '皮肤', 100, ?)", (pet_ids[0],))
        conn.execute("INSERT INTO mintmark VALUES (200, '刻印', '刻印描述')")
        conn.execute("INSERT INTO mintmark_quality VALUES (200, 5)")
        conn.execute("INSERT INTO suit VALUES (300, '套装', '套装描述')")
        conn.execute("INSERT INTO equip VALUES (400, '部件', 0, 300)")
        conn.execute("INSERT INTO equip VALUES (401, '座驾', 6, 300)")
        conn.execute("ALTER TABLE mintmark ADD COLUMN type_id INTEGER NOT NULL DEFAULT 1")
        conn.execute("ALTER TABLE mintmark ADD COLUMN rarity_id INTEGER NOT NULL DEFAULT 4")


def _add_equip_bonus(
    path: Path,
    *,
    equip_id: int,
    bonus_id: int,
    atk: int,
) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            ALTER TABLE equip ADD COLUMN bonus_id INTEGER;
            CREATE TABLE equip_bonus_attr (
                id INTEGER PRIMARY KEY,
                atk INTEGER NOT NULL,
                hp INTEGER NOT NULL,
                percent INTEGER NOT NULL
            );
            CREATE TABLE equip_bonus (
                id INTEGER PRIMARY KEY,
                desc TEXT NOT NULL,
                effect_in_use_id INTEGER,
                newse_id INTEGER,
                attribute_id INTEGER,
                hit_rate INTEGER,
                dodge_rate INTEGER,
                crit_rate INTEGER
            );
            """
        )
        conn.execute(
            'INSERT INTO equip_bonus_attr VALUES (?, ?, 0, 0)',
            (bonus_id, atk),
        )
        conn.execute(
            "INSERT INTO equip_bonus VALUES (?, '攻击加成', NULL, NULL, ?, NULL, NULL, NULL)",
            (bonus_id, bonus_id),
        )
        conn.execute(
            'UPDATE equip SET bonus_id = ? WHERE id = ?',
            (bonus_id, equip_id),
        )


def test_new_week_records_only_new_rows_and_zero_point_achievement(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1, 2))

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert state.baseline_established is True
    assert [(item.category, item.entity_id) for item in state.items] == [('pet', 2)]

    # Achievements compare by id and include zero-point rows when they are new.
    with sqlite3.connect(previous_path) as conn:
        conn.execute('DELETE FROM achievement WHERE id = 6086031')
        conn.execute('DELETE FROM title_part WHERE achievement_id = 6086031')
    state = indexer.build_release_state(current_path, previous_path, 'current-sha')
    achievement = next(item for item in state.items if item.category == 'achievement')
    assert achievement.entity_id == 6086031
    assert achievement.payload['point'] == 0
    assert achievement.payload['titles'] == [
        {'id': 177, 'name': '不动明王护法', 'original_name': '', 'ability_desc': ''}
    ]


def test_same_version_rebuild_preserves_existing_index_and_removed_rows_drop(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260731090000', pet_ids=(1, 2))
    first = indexer.build_release_state(
        current_path=previous_path, previous_path=None, current_git_sha='old'
    )
    # Simulate an already-published weekly index rather than a first baseline.
    first = indexer.ReleaseState(
        first.config_version,
        'old',
        first.weekly_cycle,
        True,
        (
            next(
                item
                for item in indexer.load_current_items(sqlite3.connect(previous_path))
                if item.category == 'pet' and item.entity_id == 2
            ),
        ),
    )
    indexer.write_release_state(previous_path, first, None)
    _create_database(current_path, version='20260731090000', pet_ids=(1,))

    state = indexer.build_release_state(current_path, previous_path, 'new')

    assert state.baseline_established is True
    assert state.items == ()


def test_same_version_source_change_is_still_indexed(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260731090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1, 2))

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert [(item.category, item.entity_id) for item in state.items] == [('pet', 2)]
    assert all(category.comparison_ready for category in state.category_states if category.category == 'pet')


def test_renumbered_item_with_same_semantic_content_is_not_new(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260731090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(2,))
    with sqlite3.connect(current_path) as conn:
        conn.execute("UPDATE pet SET name = '精灵1' WHERE id = 2")

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert all(item.category != 'pet' for item in state.items)


def test_pet_semantic_digest_ignores_weekly_pool_and_skill_definition_noise() -> None:
    before = indexer.ContentItem(
        'pet',
        1,
        '测试精灵',
        1,
        {
            'stats': {
                'type_id': 1,
                'peak_pool_id': 1,
                'peak_expert_pool_id': 2,
                'peak_pool_vote_id': 3,
            },
            'skills': [
                {
                    'id': 100,
                    'learning_level': 1,
                    'is_special': False,
                    'is_advanced': False,
                    'is_fifth': False,
                    'info': '待添加',
                }
            ],
        },
    )
    after = indexer.ContentItem(
        'pet',
        1,
        '测试精灵',
        1,
        {
            'stats': {
                'type_id': 1,
                'peak_pool_id': 0,
                'peak_expert_pool_id': 0,
                'peak_pool_vote_id': 0,
            },
            'skills': [
                {
                    'id': 100,
                    'learning_level': 1,
                    'is_special': False,
                    'is_advanced': False,
                    'is_fifth': False,
                    'info': '正式技能说明',
                }
            ],
        },
    )

    assert before.semantic_digest == after.semantic_digest

    changed_relation = indexer.replace(
        after,
        payload={
            **after.payload,
            'skills': [{**after.payload['skills'][0], 'learning_level': 5}],
        },
    )
    assert before.semantic_digest != changed_relation.semantic_digest


def test_modified_item_includes_compact_field_change_summary() -> None:
    previous = indexer.ContentItem(
        'skill',
        9000,
        '测试技能',
        9000,
        {'power': 120, 'info': '旧效果', 'pets': [{'id': 1, 'name': '精灵'}]},
    )
    current = indexer.ContentItem(
        'skill',
        9000,
        '测试技能',
        9000,
        {'power': 130, 'info': '新效果', 'pets': [{'id': 2, 'name': '其他精灵'}]},
    )

    [changed] = indexer._modified_items(
        (current,),
        (indexer.SourceSnapshotItem.from_content(previous),),
        (previous,),
        {'skill'},
    )

    assert changed.change_kind == 'modified'
    assert changed.payload['change_summary'] == [
        '技能说明：旧效果 → 新效果',
        '威力：120 → 130',
    ]


def test_peak_pool_changes_keep_zero_distinct_from_unlimited(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260807100000', pet_ids=(1, 2, 3))
    _create_database(current_path, version='20260814100000', pet_ids=(1, 2, 3))
    with sqlite3.connect(previous_path) as conn:
        conn.executemany(
            'UPDATE pet SET peak_pool_id = ? WHERE id = ?',
            ((2, 1), (3, 2), (0, 3)),
        )
    with sqlite3.connect(current_path) as conn:
        conn.executemany(
            'UPDATE pet SET peak_pool_id = ? WHERE id = ?',
            ((0, 1), (None, 2), (2, 3)),
        )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    changes = {
        item.entity_id: item.payload
        for item in state.items
        if item.category == 'peak_pool'
    }
    assert changes == {
        1: {'previous_limit': 2, 'current_limit': 0},
        2: {'previous_limit': 3, 'current_limit': None},
        3: {'previous_limit': 0, 'current_limit': 2},
    }
    assert all(
        item.change_kind == 'modified'
        for item in state.items
        if item.category == 'peak_pool'
    )


def test_peak_expert_pool_tracks_both_change_directions(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260807100000', pet_ids=(1, 2, 3))
    _create_database(current_path, version='20260814100000', pet_ids=(1, 2, 3))
    with sqlite3.connect(previous_path) as conn:
        conn.executemany(
            'UPDATE pet SET peak_expert_pool_id = ? WHERE id = ?',
            ((None, 1), (0, 2), (0, 3)),
        )
    with sqlite3.connect(current_path) as conn:
        conn.executemany(
            'UPDATE pet SET peak_expert_pool_id = ? WHERE id = ?',
            ((0, 1), (None, 2), (0, 3)),
        )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    changes = {
        item.entity_id: item.payload
        for item in state.items
        if item.category == 'peak_expert_pool'
    }
    assert changes == {
        1: {'previous_limit': None, 'current_limit': 0},
        2: {'previous_limit': 0, 'current_limit': None},
    }


def test_same_week_rebuild_preserves_peak_pool_transition_payload(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260814100000', pet_ids=(1,))
    with sqlite3.connect(previous_path) as conn:
        conn.execute('UPDATE pet SET peak_pool_id = 2 WHERE id = 1')
    baseline_path = tmp_path / 'baseline.sqlite'
    _create_database(baseline_path, version='20260807100000', pet_ids=(1,))
    with sqlite3.connect(baseline_path) as conn:
        conn.execute('UPDATE pet SET peak_pool_id = 3 WHERE id = 1')
    first = indexer.build_release_state(previous_path, baseline_path, 'first-sha')
    indexer.write_release_state(previous_path, first, None)
    _create_database(current_path, version='20260814110000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute('UPDATE pet SET peak_pool_id = 2 WHERE id = 1')

    state = indexer.build_release_state(current_path, previous_path, 'second-sha')

    change = next(item for item in state.items if item.category == 'peak_pool')
    assert change.payload == {'previous_limit': 3, 'current_limit': 2}


def test_same_week_rebuild_preserves_expert_pool_transition_payload(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260814100000', pet_ids=(1,))
    with sqlite3.connect(previous_path) as conn:
        conn.execute('UPDATE pet SET peak_expert_pool_id = 0 WHERE id = 1')
    baseline_path = tmp_path / 'baseline.sqlite'
    _create_database(baseline_path, version='20260807100000', pet_ids=(1,))
    first = indexer.build_release_state(previous_path, baseline_path, 'first-sha')
    indexer.write_release_state(previous_path, first, None)
    _create_database(current_path, version='20260814110000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute('UPDATE pet SET peak_expert_pool_id = 0 WHERE id = 1')

    state = indexer.build_release_state(current_path, previous_path, 'second-sha')

    change = next(
        item for item in state.items if item.category == 'peak_expert_pool'
    )
    assert change.payload == {'previous_limit': None, 'current_limit': 0}


def test_schema_six_recovers_expert_pool_from_previous_raw_database(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260807100000', pet_ids=(1,))
    baseline = indexer.build_release_state(previous_path, None, 'old-sha')
    legacy = indexer.replace(
        baseline,
        baseline_established=True,
        source_items=tuple(
            item
            for item in baseline.source_items
            if item.category != 'peak_expert_pool'
        ),
        source_categories=frozenset(
            category
            for category in baseline.source_categories
            if category != 'peak_expert_pool'
        ),
        category_states=tuple(
            state
            for state in baseline.category_states
            if state.category != 'peak_expert_pool'
        ),
        semantic_schema_version=5,
    )
    indexer.write_release_state(previous_path, legacy, None)
    _create_database(current_path, version='20260814100000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute('UPDATE pet SET peak_expert_pool_id = 0 WHERE id = 1')

    state = indexer.build_release_state(current_path, previous_path, 'new-sha')

    change = next(
        item for item in state.items if item.category == 'peak_expert_pool'
    )
    assert change.payload == {'previous_limit': None, 'current_limit': 0}
    assert state.semantic_schema_version == 6


def test_skill_semantic_digest_ignores_linked_pet_list() -> None:
    before = indexer.ContentItem(
        'skill',
        100,
        '测试技能',
        100,
        {'power': 100, 'info': '技能说明', 'pets': [{'id': 1}]},
    )
    after = indexer.ContentItem(
        'skill',
        100,
        '测试技能',
        100,
        {'power': 100, 'info': '技能说明', 'pets': [{'id': 2}]},
    )

    assert before.semantic_digest == after.semantic_digest
    assert before.semantic_digest != indexer.replace(
        after,
        payload={**after.payload, 'info': '修正后的技能说明'},
    ).semantic_digest


def test_mintmark_semantic_digest_ignores_rarity_but_tracks_quality() -> None:
    before = indexer.ContentItem(
        'mintmark',
        200,
        '测试刻印',
        200,
        {'desc': '官方描述', 'type_id': 1, 'rarity_id': 4, 'quality': 5},
    )

    rarity_corrected = indexer.replace(
        before,
        payload={**before.payload, 'rarity_id': 1},
    )
    quality_changed = indexer.replace(
        before,
        payload={**before.payload, 'quality': 4},
    )
    description_changed = indexer.replace(
        before,
        payload={**before.payload, 'desc': '修正后的官方描述'},
    )
    type_changed = indexer.replace(
        before,
        payload={**before.payload, 'type_id': 2},
    )

    assert before.semantic_digest == rarity_corrected.semantic_digest
    assert before.semantic_digest != quality_changed.semantic_digest
    assert before.semantic_digest != description_changed.semantic_digest
    assert before.semantic_digest != type_changed.semantic_digest


def test_equip_bonus_row_renumbering_is_not_a_content_change(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    _add_equip_bonus(previous_path, equip_id=400, bonus_id=4, atk=10)
    _add_equip_bonus(current_path, equip_id=400, bonus_id=7, atk=10)

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert not {
        (item.category, item.entity_id)
        for item in state.items
        if item.category == 'equip'
    }

    with sqlite3.connect(current_path) as conn:
        conn.execute('UPDATE equip_bonus_attr SET atk = 11 WHERE id = 7')
    changed = indexer.build_release_state(
        current_path,
        previous_path,
        'current-sha',
    )
    assert ('equip', 400, 'modified') in {
        (item.category, item.entity_id, item.change_kind) for item in changed.items
    }


def test_semantic_schema_upgrade_prunes_legacy_noise_in_same_week(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260731090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    _add_equip_bonus(previous_path, equip_id=400, bonus_id=4, atk=10)
    _add_equip_bonus(current_path, equip_id=400, bonus_id=7, atk=10)
    baseline = indexer.build_release_state(previous_path, None, 'old-sha')
    equip = next(
        item
        for item in indexer.load_current_items(sqlite3.connect(previous_path))
        if item.category == 'equip' and item.entity_id == 400
    )
    legacy = indexer.replace(
        baseline,
        baseline_established=True,
        items=(equip.with_change_kind('modified'),),
        semantic_schema_version=1,
    )
    indexer.write_release_state(previous_path, legacy, None)

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert all(item.category != 'equip' for item in state.items)


def test_semantic_v3_migration_prunes_rarity_only_mintmarks_and_keeps_additions(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260731090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute('UPDATE mintmark SET rarity_id = 1 WHERE id = 200')
        conn.execute(
            """
            INSERT INTO mintmark (id, name, desc, type_id, rarity_id)
            VALUES (201, '新增刻印', '新增刻印描述', 2, 1)
            """
        )
        conn.execute('INSERT INTO mintmark_quality VALUES (201, 5)')

    baseline = indexer.build_release_state(previous_path, None, 'old-sha')
    legacy_mintmark = next(
        item
        for item in indexer.load_current_items(sqlite3.connect(previous_path))
        if item.category == 'mintmark' and item.entity_id == 200
    )
    legacy = indexer.replace(
        baseline,
        baseline_established=True,
        items=(legacy_mintmark.with_change_kind('modified'),),
        semantic_schema_version=2,
    )
    indexer.write_release_state(previous_path, legacy, None)

    state = indexer.build_release_state(
        current_path,
        previous_path,
        'current-sha',
        (indexer.SourceHistoryAddition('mintmark', 201),),
    )

    assert [(item.category, item.entity_id, item.change_kind) for item in state.items] == [
        ('mintmark', 201, 'added')
    ]
    assert state.items[0].payload == {
        'desc': '新增刻印描述',
        'type_id': 2,
        'rarity_id': 1,
        'quality': 5,
    }


def test_semantic_v3_migration_keeps_real_skill_changes_from_v2_snapshot(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260731090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute("UPDATE skill SET info = '正式技能说明' WHERE id = 9000")

    baseline = indexer.build_release_state(previous_path, None, 'old-sha')
    legacy = indexer.replace(
        baseline,
        baseline_established=True,
        semantic_schema_version=2,
    )
    indexer.write_release_state(previous_path, legacy, None)

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert ('skill', 9000, 'modified') in {
        (item.category, item.entity_id, item.change_kind) for item in state.items
    }


def test_semantic_v4_migration_prunes_equip_parser_corrections_and_keeps_additions(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260814104752', pet_ids=(1,))
    _create_database(current_path, version='20260814104752', pet_ids=(1,))
    _add_equip_bonus(previous_path, equip_id=400, bonus_id=4, atk=50)
    _add_equip_bonus(current_path, equip_id=400, bonus_id=7, atk=50)
    with sqlite3.connect(current_path) as conn:
        conn.execute('UPDATE equip_bonus_attr SET atk = 0, hp = 50 WHERE id = 7')
        conn.execute("INSERT INTO equip VALUES (402, '真正新增腰带', 2, 0, NULL)")

    baseline = indexer.build_release_state(previous_path, None, 'old-sha')
    legacy_equip = next(
        item
        for item in indexer.load_current_items(sqlite3.connect(previous_path))
        if item.category == 'equip' and item.entity_id == 400
    )
    legacy = indexer.replace(
        baseline,
        baseline_established=True,
        items=(legacy_equip.with_change_kind('modified'),),
        semantic_schema_version=3,
    )
    indexer.write_release_state(previous_path, legacy, None)

    state = indexer.build_release_state(
        current_path,
        previous_path,
        'current-sha',
        (indexer.SourceHistoryAddition('equip', 402),),
    )

    assert state.semantic_schema_version == 6
    assert [(item.category, item.entity_id, item.change_kind) for item in state.items] == [
        ('equip', 402, 'added')
    ]


def test_same_week_accumulates_incremental_rows(tmp_path: Path) -> None:
    prior_raw = tmp_path / 'prior-raw.sqlite'
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(prior_raw, version='20260725090000', pet_ids=(1,))
    _create_database(previous_path, version='20260729090000', pet_ids=(1, 2))
    prior_state = indexer.build_release_state(previous_path, prior_raw, 'old')
    indexer.write_release_state(previous_path, prior_state, None)
    _create_database(current_path, version='20260730090000', pet_ids=(1, 2, 3))

    state = indexer.build_release_state(current_path, previous_path, 'new')

    assert [(item.category, item.entity_id) for item in state.items] == [
        ('pet', 2),
        ('pet', 3),
    ]


def test_existing_entity_content_changes_are_marked_modified(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute("UPDATE pet SET name = '调整后的精灵' WHERE id = 1")

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert ('pet', 1, 'modified') in {
        (item.category, item.entity_id, item.change_kind) for item in state.items
    }
    assert all(item.category != 'pet_skin' for item in state.items)


def test_new_skills_include_their_available_payload(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute(
            "INSERT INTO skill VALUES (9001, '新增技能', '新增技能效果')"
        )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    skill = next(item for item in state.items if item.category == 'skill')
    assert skill.entity_id == 9001
    assert skill.name == '新增技能'
    assert skill.payload['info'] == '新增技能效果'


def test_new_category_uses_previous_raw_table_as_its_source_snapshot(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    baseline = indexer.build_release_state(previous_path, None, 'old')
    indexer.write_release_state(previous_path, baseline, None)
    with sqlite3.connect(previous_path) as conn:
        conn.execute("DELETE FROM new_content_source_snapshot WHERE category = 'skill'")
        conn.execute("DELETE FROM new_content_source_category WHERE category = 'skill'")
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.execute("INSERT INTO skill VALUES (9001, '新增技能', '新增技能效果')")

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    categories = {item.category: item for item in state.category_states}
    assert categories['skill'].comparison_ready is True
    assert ('skill', 9001) in {(item.category, item.entity_id) for item in state.items}


def test_source_history_additions_repair_an_overwritten_same_version_baseline(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    additions_path = tmp_path / 'additions.json'
    _create_database(previous_path, version='20260730210447', pet_ids=(1, 2))
    baseline = indexer.build_release_state(previous_path, None, 'old')
    indexer.write_release_state(previous_path, baseline, None)
    _create_database(current_path, version='20260730210447', pet_ids=(1, 2))
    additions_path.write_text(
        '{"additions": [{"category": "pet", "entity_id": 2}]}',
        encoding='utf-8',
    )

    state = indexer.build_release_state(
        current_path,
        previous_path,
        'current-sha',
        indexer.load_source_history_additions(additions_path),
    )

    assert [(item.category, item.entity_id, item.change_kind) for item in state.items] == [
        ('pet', 2, 'added')
    ]


def test_source_history_addition_is_deduplicated_from_new_cycle_diff(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1, 2))

    state = indexer.build_release_state(
        current_path,
        previous_path,
        'current-sha',
        (indexer.SourceHistoryAddition('pet', 2),),
    )

    assert [(item.category, item.entity_id, item.change_kind) for item in state.items] == [
        ('pet', 2, 'added')
    ]


def test_source_history_additions_route_equip_mounts_to_the_runtime_category(
    tmp_path: Path,
) -> None:
    database = tmp_path / 'current.sqlite'
    _create_database(database, version='20260730210447', pet_ids=(1,))
    with sqlite3.connect(database) as conn:
        current = indexer.load_current_items(conn)

    items = indexer._source_history_items(
        current,
        (indexer.SourceHistoryAddition('equip', 401),),
    )

    assert [(item.category, item.entity_id, item.change_kind) for item in items] == [
        ('mount', 401, 'added')
    ]


def test_first_autocard_tables_are_not_reported_as_new(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    with sqlite3.connect(current_path) as conn:
        conn.executescript(
            """
            CREATE TABLE autocard_card (id INTEGER PRIMARY KEY, name TEXT, raw_json TEXT);
            CREATE TABLE autocard_role (id INTEGER PRIMARY KEY, name TEXT, raw_json TEXT);
            INSERT INTO autocard_card VALUES (1, '卡牌一号', '{"id": 1, "cardTxt": "原效果"}');
            INSERT INTO autocard_role VALUES (1, '角色一号', '{"id": 1, "skillTxt": "原技能"}');
            """
        )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert not {
        (item.category, item.entity_id)
        for item in state.items
        if item.category in {'autocard_card', 'autocard_role'}
    }
    states = {item.category: item for item in state.category_states}
    assert states['autocard_card'].reason == 'first_observation'
    assert states['autocard_role'].reason == 'first_observation'


def test_autocard_cards_and_roles_keep_separate_id_spaces(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    for path, card_name, role_name in (
        (previous_path, '旧卡牌', '旧角色'),
        (current_path, '新卡牌', '新角色'),
    ):
        with sqlite3.connect(path) as conn:
            conn.executescript(
                """
                CREATE TABLE autocard_card (id INTEGER PRIMARY KEY, name TEXT, raw_json TEXT);
                CREATE TABLE autocard_role (id INTEGER PRIMARY KEY, name TEXT, raw_json TEXT);
                """
            )
            conn.execute(
                "INSERT INTO autocard_card VALUES (1, ?, ?)",
                (card_name, f'{{"id": 1, "cardTxt": "{card_name}"}}'),
            )
            conn.execute(
                "INSERT INTO autocard_role VALUES (1, ?, ?)",
                (role_name, f'{{"id": 1, "skillTxt": "{role_name}"}}'),
            )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert {(item.category, item.entity_id) for item in state.items} >= {
        ('autocard_card', 1),
        ('autocard_role', 1),
    }


@pytest.mark.parametrize(
    ('field', 'before', 'after'),
    [
        ('skillTxt', '原技能', '新技能'),
        ('skillName', '原技能名', '新技能名'),
        ('skillUpgrade', '原祝印', '新祝印'),
        ('picID', 7, 8),
        ('desc', '原描述', '新描述'),
    ],
)
def test_official_autocard_role_sidecar_changes_are_marked_modified(
    tmp_path: Path,
    field: str,
    before: object,
    after: object,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    base_role = {
        'id': 1,
        'name': '测试角色',
        'skillTxt': '原技能',
        'skillName': '原技能名',
        'skillUpgrade': '原祝印',
        'picID': 7,
        'desc': '原描述',
    }
    for path, value in ((previous_path, before), (current_path, after)):
        role = {**base_role, field: value}
        with sqlite3.connect(path) as conn:
            conn.executescript(
                '''
                CREATE TABLE autocard_role (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL
                );
                CREATE TABLE autocard_role_raw (
                    role_id INTEGER PRIMARY KEY,
                    raw_json TEXT NOT NULL
                );
                '''
            )
            conn.execute(
                'INSERT INTO autocard_role VALUES (?, ?, ?)',
                (1, '测试角色', str(role['desc'])),
            )
            conn.execute(
                'INSERT INTO autocard_role_raw VALUES (?, ?)',
                (1, json.dumps(role, ensure_ascii=False)),
            )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert ('autocard_role', 1, 'modified') in {
        (item.category, item.entity_id, item.change_kind) for item in state.items
    }


def test_autocard_effect_change_is_marked_modified(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    for path, effect in ((previous_path, '旧效果'), (current_path, '新效果')):
        with sqlite3.connect(path) as conn:
            conn.executescript(
                'CREATE TABLE autocard_card (id INTEGER PRIMARY KEY, name TEXT, raw_json TEXT);'
            )
            conn.execute(
                "INSERT INTO autocard_card VALUES (1, '测试卡牌', ?)",
                (f'{{"id": 1, "cardTxt": "{effect}"}}',),
            )

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert ('autocard_card', 1, 'modified') in {
        (item.category, item.entity_id, item.change_kind) for item in state.items
    }


def _add_autocard_sanctuary_effects(path: Path, *, effect: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            f'''
            CREATE TABLE autocard_season_effect (
                id INTEGER PRIMARY KEY, sanctuary_id INTEGER, name TEXT,
                description TEXT, buff_id TEXT, buff_param TEXT,
                count_buff_id TEXT, count_type INTEGER, count_num INTEGER,
                unlock_round INTEGER, pic_id INTEGER, season_id INTEGER,
                stage INTEGER
            );
            INSERT INTO autocard_season_effect VALUES
                (8, 2, '沧岚', '基础圣域', '', '', '', 0, 0, 0, 3105, 1, 0),
                (9, 2, '潮涌', '{effect}', '50041', '1', '', 0, 0, 5, 0, 1, 1);
            '''
        )
        conn.execute("UPDATE pet SET name = '沧岚之王' WHERE id = 1")
        conn.execute("UPDATE autocard_season_effect SET pic_id = 1 WHERE id = 8")


def test_first_sanctuary_effect_table_establishes_its_own_baseline(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    _add_autocard_sanctuary_effects(current_path, effect='潮涌效果')

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert all(item.category != 'autocard_sanctuary_effect' for item in state.items)
    sanctuary = next(
        category
        for category in state.category_states
        if category.category == 'autocard_sanctuary_effect'
    )
    assert sanctuary.comparison_ready is False
    assert sanctuary.reason == 'first_observation'


def test_source_snapshot_is_reused_when_previous_index_is_rebuilt(tmp_path: Path) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    first = indexer.build_release_state(previous_path, None, 'old-sha')
    indexer.write_release_state(previous_path, first, None)
    _create_database(current_path, version='20260731090000', pet_ids=(1, 2))

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    assert [(item.category, item.entity_id) for item in state.items] == [('pet', 2)]
    assert len(state.source_items) == len(indexer.load_current_items(sqlite3.connect(current_path)))


def test_sanctuary_effect_changes_are_indexed_with_sanctuary_context(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1,))
    _add_autocard_sanctuary_effects(previous_path, effect='旧效果')
    _add_autocard_sanctuary_effects(current_path, effect='新效果')

    state = indexer.build_release_state(current_path, previous_path, 'current-sha')

    item = next(
        item
        for item in state.items
        if item.category == 'autocard_sanctuary_effect' and item.entity_id == 9
    )
    assert item.change_kind == 'modified'
    assert item.payload['sanctuary_name'] == '沧岚'
    assert item.payload['sanctuary_pet_name'] == '沧岚之王'
