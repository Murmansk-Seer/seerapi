import sqlite3

from scripts.autocard_asset_manifest import collect_autocard_asset_requests


def test_normalized_role_schema_does_not_suppress_card_or_chip_assets() -> None:
    with sqlite3.connect(':memory:') as conn:
        conn.executescript("""
            CREATE TABLE autocard_card (id INTEGER, raw_json TEXT);
            INSERT INTO autocard_card VALUES (1, '{"picID": 1}');
            CREATE TABLE autocard_role (id INTEGER, name TEXT);
            CREATE TABLE autocard_role_raw (role_id INTEGER, pic_id INTEGER);
            INSERT INTO autocard_role_raw VALUES (3, 9);
            CREATE TABLE autocard_chip (id INTEGER);
            INSERT INTO autocard_chip VALUES (115);
        """)
        requests = collect_autocard_asset_requests(conn)
        assert requests is not None
        assert {(item.asset_kind, item.asset_key) for item in requests} == {
            ('autocard_card', 'card_1'),
            ('autocard_role', 'role_9'),
            ('autocard_chip', 'autocardChip_115'),
        }


def test_chip_assets_survive_missing_card_and_role_tables() -> None:
    with sqlite3.connect(':memory:') as conn:
        conn.executescript(
            'CREATE TABLE autocard_chip (id INTEGER); INSERT INTO autocard_chip VALUES (115);'
        )
        requests = collect_autocard_asset_requests(conn)
        assert requests is not None
        assert [(item.asset_kind, item.asset_key) for item in requests] == [
            ('autocard_chip', 'autocardChip_115')
        ]


def test_chip_assets_are_optional_and_use_official_sprite_ids() -> None:
    with sqlite3.connect(':memory:') as conn:
        conn.executescript("""
            CREATE TABLE autocard_card (id INTEGER, raw_json TEXT);
            CREATE TABLE autocard_role (id INTEGER, pic_id INTEGER);
        """)
        assert collect_autocard_asset_requests(conn) == ()
        conn.executescript("""
            CREATE TABLE autocard_chip (id INTEGER);
            INSERT INTO autocard_chip VALUES (115), (116), (0);
        """)
        requests = collect_autocard_asset_requests(conn)
        assert requests is not None
        assert [(item.asset_kind, item.asset_key, item.path) for item in requests] == [
            (
                'autocard_chip',
                f'autocardChip_{value}',
                f'newseer/assets/game/ui/autocard/s2chip/autocardChip_{value}.png',
            )
            for value in (115, 116)
        ]
