import importlib.util
from pathlib import Path
import sqlite3
import sys

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
            CREATE TABLE pet (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE pet_skin (
                id INTEGER PRIMARY KEY, name TEXT, resource_id INTEGER, pet_id INTEGER
            );
            CREATE TABLE mintmark (id INTEGER PRIMARY KEY, name TEXT, desc TEXT);
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
            'INSERT INTO pet VALUES (?, ?)',
            [(item, f'精灵{item}') for item in pet_ids],
        )
        conn.execute("INSERT INTO pet_skin VALUES (100, '皮肤', 100, ?)", (pet_ids[0],))
        conn.execute("INSERT INTO mintmark VALUES (200, '刻印', '刻印描述')")
        conn.execute("INSERT INTO suit VALUES (300, '套装', '套装描述')")
        conn.execute("INSERT INTO equip VALUES (400, '部件', 0, 300)")
        conn.execute("INSERT INTO equip VALUES (401, '座驾', 6, 300)")


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


def test_new_week_promotes_the_previous_latest_as_weekly_baseline(
    tmp_path: Path,
) -> None:
    previous_path = tmp_path / 'previous.sqlite'
    current_path = tmp_path / 'current.sqlite'
    _create_database(previous_path, version='20260724090000', pet_ids=(1,))
    _create_database(current_path, version='20260731090000', pet_ids=(1, 2))

    state = indexer.build_release_state(current_path, previous_path, 'new')
    previous = indexer._load_previous_state(previous_path)

    assert previous is not None
    assert indexer.should_promote_previous(state, previous) is True


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


def test_autocard_cards_and_roles_keep_separate_id_spaces(tmp_path: Path) -> None:
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

    assert {(item.category, item.entity_id) for item in state.items} >= {
        ('autocard_card', 1),
        ('autocard_role', 1),
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
