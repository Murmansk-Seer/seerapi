#!/usr/bin/env python3
"""Build the weekly new-content index embedded in the IronsBot data SQLite.

The rolling GitHub release keeps only the latest database.  This script runs
before that release is overwritten, compares the newly-built database with the
previous published one, and embeds the result into the new database.  Runtime
bot instances therefore do not need a local history database.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3

from new_content_index_models import (
    CATEGORY_SOURCE_TABLES,
    CONTENT_CATEGORIES,
    SEMANTIC_SCHEMA_VERSION,
    CategoryState,
    ContentItem,
    ReleaseState,
    SourceHistoryAddition,
    SourceSnapshotItem,
    semantic_migration_categories,
    semantic_migration_prune_categories,
)
from new_content_index_snapshot import (
    _has_table,
    _table_columns,
    load_current_items,
)

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


def load_source_history_additions(path: Path | None) -> tuple[SourceHistoryAddition, ...]:
    """Load Git-confirmed additions without treating source-file edits as changes.

    The API data repository records both real content additions and broad schema
    rewrites. The workflow only writes numeric entities created by Git, so this
    input may safely repair a rolling SQLite baseline that was overwritten after
    an official update became available.
    """
    if path is None or not path.is_file():
        return ()
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ValueError(f'invalid source-history additions: {path}') from error
    raw_additions = document.get('additions', []) if isinstance(document, dict) else []
    if not isinstance(raw_additions, list):
        raise ValueError(f'invalid source-history additions: {path}')
    additions: set[SourceHistoryAddition] = set()
    valid_categories = set(CONTENT_CATEGORIES)
    for raw in raw_additions:
        if not isinstance(raw, dict):
            raise ValueError(f'invalid source-history addition: {raw!r}')
        category = raw.get('category')
        entity_id = raw.get('entity_id')
        if (
            not isinstance(category, str)
            or category not in valid_categories
            or isinstance(entity_id, bool)
            or not isinstance(entity_id, int)
            or entity_id <= 0
        ):
            raise ValueError(f'invalid source-history addition: {raw!r}')
        additions.add(SourceHistoryAddition(category, entity_id))
    return tuple(sorted(additions, key=lambda item: (item.category, item.entity_id)))


def _new_items(
    current: tuple[ContentItem, ...], previous: tuple[SourceSnapshotItem, ...],
    comparable_categories: set[str],
) -> tuple[ContentItem, ...]:
    previous_by_id = {(item.category, item.entity_id) for item in previous}
    previous_semantic = {item.semantic_digest for item in previous}
    return tuple(
        item.with_change_kind('added')
        for item in current
        if item.category in comparable_categories
        and (item.category, item.entity_id) not in previous_by_id
        and item.semantic_digest not in previous_semantic
    )


def _modified_items(
    current: tuple[ContentItem, ...], previous: tuple[SourceSnapshotItem, ...],
    comparable_categories: set[str],
) -> tuple[ContentItem, ...]:
    previous_by_id = {
        (item.category, item.entity_id): item.semantic_digest for item in previous
    }
    return tuple(
        item.with_change_kind('modified')
        for item in current
        if (previous_item := previous_by_id.get((item.category, item.entity_id)))
        is not None
        and item.category in comparable_categories
        and item.semantic_digest != previous_item
    )


def _source_history_items(
    current: tuple[ContentItem, ...],
    additions: Iterable[SourceHistoryAddition],
) -> tuple[ContentItem, ...]:
    """Resolve Git additions through the current SQLite presentation payload."""
    current_by_id = {(item.category, item.entity_id): item for item in current}
    resolved: list[ContentItem] = []
    for addition in additions:
        categories = (addition.category,)
        if addition.category == 'equip':
            # The source API keeps mounts in the equip collection while the
            # runtime index deliberately presents them as their own category.
            categories = ('equip', 'mount')
        for category in categories:
            if item := current_by_id.get((category, addition.entity_id)):
                resolved.append(item.with_change_kind('added'))
                break
    return tuple(resolved)


def _current_subset(
    candidates: Iterable[ContentItem], current: tuple[ContentItem, ...]
) -> tuple[ContentItem, ...]:
    current_by_id = {(item.category, item.entity_id): item for item in current}
    change_kinds = {
        (item.category, item.entity_id): item.change_kind for item in candidates
    }
    return tuple(
        sorted(
            (
                current_by_id[key].with_change_kind(change_kind)
                for key, change_kind in change_kinds.items()
                if key in current_by_id
            ),
            key=lambda item: (item.category, item.entity_id),
        )
    )


def _category_states(
    current_categories: frozenset[str],
    previous_categories: frozenset[str],
) -> tuple[CategoryState, ...]:
    states: list[CategoryState] = []
    for category in CONTENT_CATEGORIES:
        if category not in current_categories:
            states.append(CategoryState(category, False, 'source_unavailable'))
        elif category not in previous_categories:
            states.append(CategoryState(category, False, 'first_observation'))
        else:
            states.append(CategoryState(category, True, 'ready'))
    return tuple(states)


def build_release_state(
    current_path: Path,
    previous_path: Path | None,
    current_git_sha: str,
    source_history_additions: Iterable[SourceHistoryAddition] = (),
) -> ReleaseState:
    with sqlite3.connect(current_path) as conn:
        current_version = _config_version(conn)
        current_items = load_current_items(conn)
        current_categories = _source_categories(conn)
    current_sources = tuple(
        SourceSnapshotItem.from_content(item) for item in current_items
    )
    previous = _load_previous_state(previous_path)
    cycle = _weekly_cycle(current_version)
    if previous is None:
        return ReleaseState(
            current_version,
            current_git_sha,
            cycle,
            False,
            (),
            current_sources,
            current_categories,
            _category_states(current_categories, frozenset()),
        )
    category_states = _category_states(
        current_categories,
        previous.source_categories,
    )
    comparable_categories = {
        state.category for state in category_states if state.comparison_ready
    }
    increment = _current_subset(
        (
            *_new_items(current_items, previous.source_items, comparable_categories),
            *_modified_items(
                current_items,
                previous.source_items,
                comparable_categories,
            ),
            *_source_history_items(current_items, source_history_additions),
        ),
        current_items,
    )
    if previous.weekly_cycle == cycle:
        carried_items = previous.items
        if previous.semantic_schema_version < SEMANTIC_SCHEMA_VERSION:
            migration_prune_categories = semantic_migration_prune_categories(
                previous.semantic_schema_version
            )
            carried_items = tuple(
                item
                for item in carried_items
                if not (
                    item.change_kind == 'modified'
                    and item.category in migration_prune_categories
                )
            )
        items = _current_subset((*carried_items, *increment), current_items)
    else:
        items = increment
    return ReleaseState(
        current_version,
        current_git_sha,
        cycle,
        True,
        items,
        current_sources,
        current_categories,
        category_states,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument(
        '--source-history-additions',
        type=Path,
        help='Git-confirmed entity additions from the published API source history.',
    )
    parser.add_argument('--current-git-sha', required=True)
    parser.add_argument(
        '--github-output',
        type=Path,
        help='Optional GitHub Actions output file for release promotion metadata.',
    )
    args = parser.parse_args()

    previous = _load_previous_state(args.previous)
    history_additions = load_source_history_additions(args.source_history_additions)
    state = build_release_state(
        args.current,
        args.previous,
        args.current_git_sha,
        history_additions,
    )
    write_release_state(args.current, state, previous)
    if args.github_output is not None:
        with args.github_output.open('a', encoding='utf-8') as output:
            output.write(f'weekly_cycle={state.weekly_cycle}\n')
            output.write(
                f'baseline_established={str(state.baseline_established).lower()}\n'
            )
    ready_categories = sum(
        1 for category in state.category_states if category.comparison_ready
    )
    status = 'ready' if state.baseline_established else 'history-unavailable'
    print(  # noqa: T201 - CLI status is required by the GitHub Actions log.
        'new-content index: '
        f'status={status} cycle={state.weekly_cycle} '
        f'items={len(state.items)} comparable_categories={ready_categories}'
    )


if __name__ == '__main__':
    main()
