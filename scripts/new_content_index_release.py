"""Read and write the persisted weekly new-content release state."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from new_content_index_models import (
    CATEGORY_SOURCE_TABLES,
    SEMANTIC_SCHEMA_VERSION,
    CategoryState,
    ContentItem,
    ReleaseState,
    SourceSnapshotItem,
    semantic_migration_categories,
)
from new_content_index_snapshot import _has_table, _table_columns, load_current_items

RELEASE_TABLE = 'new_content_release'
ITEM_TABLE = 'new_content_item'
SOURCE_SNAPSHOT_TABLE = 'new_content_source_snapshot'
CATEGORY_SNAPSHOT_TABLE = 'new_content_source_category'
CATEGORY_STATE_TABLE = 'new_content_category_state'


def _metadata_value(conn: sqlite3.Connection, key: str) -> str | None:
    if not _has_table(conn, 'ironsbot_metadata'):
        return None
    row = conn.execute(
        'SELECT value FROM ironsbot_metadata WHERE key = ?', (key,)
    ).fetchone()
    return str(row[0]) if row else None


def _config_version(conn: sqlite3.Connection) -> str:
    value = _metadata_value(conn, 'config_package_version')
    if value:
        return value
    if _has_table(conn, 'api_metadata'):
        row = conn.execute(
            'SELECT data_version, generate_time FROM api_metadata ORDER BY id DESC LIMIT 1'
        ).fetchone()
        if row:
            return str(row[0] or row[1] or 'unknown')
    return 'unknown'


def _version_date(version: str) -> date:
    digits = ''.join(char for char in version if char.isdigit())
    if len(digits) >= 14:
        try:
            return (
                datetime.strptime(digits[:14], '%Y%m%d%H%M%S')
                .replace(tzinfo=timezone.utc)
                .astimezone(ZoneInfo('Asia/Shanghai'))
                .date()
            )
        except ValueError:
            pass
    if len(digits) >= 8:
        try:
            return datetime.strptime(digits[:8], '%Y%m%d').date()
        except ValueError:
            pass
    return datetime.now().date()


def _weekly_cycle(version: str) -> str:
    """Return the Friday-starting weekly cycle containing the source version."""
    value = _version_date(version)
    friday = value - timedelta(days=(value.weekday() - 4) % 7)
    return friday.isoformat()


def _load_previous_state(path: Path | None) -> ReleaseState | None:
    if path is None or not path.is_file():
        return None
    with sqlite3.connect(path) as conn:
        version = _config_version(conn)
        source_items = _load_source_snapshot(conn)
        source_categories = _load_source_categories(conn)
        current_items = load_current_items(conn)
        current_categories = _source_categories(conn)
        release_columns = (
            _table_columns(conn, RELEASE_TABLE)
            if _has_table(conn, RELEASE_TABLE)
            else set()
        )
        semantic_schema_version = 1
        if 'schema_version' in release_columns:
            version_row = conn.execute(
                f'SELECT schema_version FROM {RELEASE_TABLE} WHERE id = 1'
            ).fetchone()
            if version_row is not None:
                semantic_schema_version = int(version_row[0])
        if not source_items:
            source_items = tuple(
                SourceSnapshotItem.from_content(item) for item in current_items
            )
        else:
            missing_categories = current_categories - source_categories
            source_items = (*source_items, *(
                SourceSnapshotItem.from_content(item)
                for item in current_items
                if item.category in missing_categories
            ))
            if semantic_schema_version < SEMANTIC_SCHEMA_VERSION:
                migration_categories = semantic_migration_categories(
                    semantic_schema_version
                )
                source_items = (
                    *(
                        item
                        for item in source_items
                        if item.category not in migration_categories
                    ),
                    *(
                        SourceSnapshotItem.from_content(item)
                        for item in current_items
                        if item.category in migration_categories
                    ),
                )
        source_categories = source_categories | current_categories
        if not _has_table(conn, RELEASE_TABLE):
            return ReleaseState(
                version,
                None,
                _weekly_cycle(version),
                False,
                (),
                source_items,
                source_categories,
                semantic_schema_version=semantic_schema_version,
                raw_items=current_items,
            )
        row = conn.execute(
            f'SELECT current_git_sha, weekly_cycle, baseline_established FROM {RELEASE_TABLE} WHERE id = 1'
        ).fetchone()
        if row is None:
            return ReleaseState(
                version,
                None,
                _weekly_cycle(version),
                False,
                (),
                source_items,
                source_categories,
                semantic_schema_version=semantic_schema_version,
                raw_items=current_items,
            )
        item_columns = {
            str(row[1])
            for row in conn.execute(f'PRAGMA table_info({ITEM_TABLE})').fetchall()
        }
        change_kind_column = (
            'change_kind' if 'change_kind' in item_columns else "'added' AS change_kind"
        )
        items = tuple(
            ContentItem(
                category=str(item[0]),
                entity_id=int(item[1]),
                name=str(item[2]),
                sort_value=int(item[3]),
                payload=json.loads(str(item[4])),
                change_kind=str(item[5]),
            )
            for item in conn.execute(
                f"""
                SELECT category, entity_id, name, sort_value, payload_json,
                       {change_kind_column}
                FROM {ITEM_TABLE}
                """
            )
        )
        return ReleaseState(
            version,
            str(row[0]) if row[0] else None,
            str(row[1] or _weekly_cycle(version)),
            bool(row[2]),
            items,
            source_items,
            source_categories,
            _load_category_states(conn),
            semantic_schema_version,
            current_items,
        )


def _load_source_snapshot(conn: sqlite3.Connection) -> tuple[SourceSnapshotItem, ...]:
    if not _has_table(conn, SOURCE_SNAPSHOT_TABLE):
        return ()
    return tuple(
        SourceSnapshotItem(str(row[0]), int(row[1]), str(row[2]))
        for row in conn.execute(
            f'''
            SELECT category, entity_id, semantic_digest
            FROM {SOURCE_SNAPSHOT_TABLE}
            ORDER BY category, entity_id
            '''
        )
    )


def _load_source_categories(conn: sqlite3.Connection) -> frozenset[str]:
    if not _has_table(conn, CATEGORY_SNAPSHOT_TABLE):
        return frozenset()
    return frozenset(
        str(row[0])
        for row in conn.execute(
            f'SELECT category FROM {CATEGORY_SNAPSHOT_TABLE}'
        )
    )


def _source_categories(conn: sqlite3.Connection) -> frozenset[str]:
    return frozenset(
        category
        for category, tables in CATEGORY_SOURCE_TABLES.items()
        if all(_has_table(conn, table) for table in tables)
    )


def _load_category_states(conn: sqlite3.Connection) -> tuple[CategoryState, ...]:
    if not _has_table(conn, CATEGORY_STATE_TABLE):
        return ()
    return tuple(
        CategoryState(str(row[0]), bool(row[1]), str(row[2]))
        for row in conn.execute(
            f'''
            SELECT category, comparison_ready, reason
            FROM {CATEGORY_STATE_TABLE}
            ORDER BY category
            '''
        )
    )



def write_release_state(
    path: Path,
    state: ReleaseState,
    previous: ReleaseState | None,
) -> None:
    generated_at = datetime.now().astimezone().isoformat(timespec='seconds')
    with sqlite3.connect(path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS {RELEASE_TABLE}')
        conn.execute(f'DROP TABLE IF EXISTS {ITEM_TABLE}')
        conn.execute(f'DROP TABLE IF EXISTS {SOURCE_SNAPSHOT_TABLE}')
        conn.execute(f'DROP TABLE IF EXISTS {CATEGORY_SNAPSHOT_TABLE}')
        conn.execute(f'DROP TABLE IF EXISTS {CATEGORY_STATE_TABLE}')
        conn.execute(
            f"""
            CREATE TABLE {RELEASE_TABLE} (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                current_config_version TEXT NOT NULL,
                previous_config_version TEXT,
                current_git_sha TEXT NOT NULL,
                previous_git_sha TEXT,
                weekly_cycle TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                baseline_established INTEGER NOT NULL,
                schema_version INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE {SOURCE_SNAPSHOT_TABLE} (
                category TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                semantic_digest TEXT NOT NULL,
                PRIMARY KEY (category, entity_id)
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE {CATEGORY_SNAPSHOT_TABLE} (
                category TEXT PRIMARY KEY
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE {CATEGORY_STATE_TABLE} (
                category TEXT PRIMARY KEY,
                comparison_ready INTEGER NOT NULL,
                reason TEXT NOT NULL
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE {ITEM_TABLE} (
                category TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sort_value INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                change_kind TEXT NOT NULL CHECK (change_kind IN ('added', 'modified')),
                PRIMARY KEY (category, entity_id)
            )
            """
        )
        conn.execute(
            f"""
            INSERT INTO {RELEASE_TABLE}
                (id, current_config_version, previous_config_version,
                 current_git_sha, previous_git_sha, weekly_cycle, generated_at,
                 baseline_established, schema_version)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                state.config_version,
                previous.config_version if previous else None,
                state.git_sha or 'unknown',
                previous.git_sha if previous else None,
                state.weekly_cycle,
                generated_at,
                int(state.baseline_established),
                state.semantic_schema_version,
            ),
        )
        conn.executemany(
            f"""
            INSERT INTO {ITEM_TABLE}
                (category, entity_id, name, sort_value, payload_json, change_kind)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.category,
                    item.entity_id,
                    item.name,
                    item.sort_value,
                    item.payload_json,
                    item.change_kind,
                )
                for item in state.items
            ],
        )
        conn.executemany(
            f"""
            INSERT INTO {SOURCE_SNAPSHOT_TABLE}
                (category, entity_id, semantic_digest)
            VALUES (?, ?, ?)
            """,
            [
                (item.category, item.entity_id, item.semantic_digest)
                for item in state.source_items
            ],
        )
        conn.executemany(
            f'INSERT INTO {CATEGORY_SNAPSHOT_TABLE} (category) VALUES (?)',
            [(category,) for category in sorted(state.source_categories)],
        )
        conn.executemany(
            f"""
            INSERT INTO {CATEGORY_STATE_TABLE}
                (category, comparison_ready, reason)
            VALUES (?, ?, ?)
            """,
            [
                (state.category, int(state.comparison_ready), state.reason)
                for state in state.category_states
            ],
        )
        conn.execute(
            f'CREATE INDEX idx_{ITEM_TABLE}_category_sort ON {ITEM_TABLE} (category, sort_value)'
        )
        conn.commit()


