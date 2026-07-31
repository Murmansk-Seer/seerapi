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
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any

RELEASE_TABLE = 'new_content_release'
ITEM_TABLE = 'new_content_item'


@dataclass(frozen=True)
class ContentItem:
    category: str
    entity_id: int
    name: str
    sort_value: int
    payload: dict[str, Any]
    change_kind: str = 'added'

    @property
    def payload_json(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False, sort_keys=True)

    @property
    def semantic_key(self) -> str:
        """A stable fallback for an upstream item whose numeric id changed."""
        payload = self.payload
        if self.category == 'pet_skin':
            # The linked pet name is presentation-only. A pet change must not
            # make every one of its skins look modified.
            payload = {
                key: value for key, value in payload.items() if key != 'pet_name'
            }
        return json.dumps(
            {
                'category': self.category,
                'name': self.name,
                'payload': payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def with_change_kind(self, change_kind: str) -> 'ContentItem':
        return replace(self, change_kind=change_kind)


@dataclass(frozen=True)
class ReleaseState:
    config_version: str
    git_sha: str | None
    weekly_cycle: str
    baseline_established: bool
    items: tuple[ContentItem, ...]


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info({table})')}


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


def _rows(conn: sqlite3.Connection, query: str) -> Iterable[sqlite3.Row]:
    return conn.execute(query).fetchall()


def load_current_items(conn: sqlite3.Connection) -> tuple[ContentItem, ...]:
    conn.row_factory = sqlite3.Row
    items: list[ContentItem] = []

    title_by_achievement: dict[int, list[dict[str, Any]]] = {}
    if _has_table(conn, 'title_part'):
        for row in _rows(
            conn,
            'SELECT id, name, original_name, ability_desc, achievement_id FROM title_part',
        ):
            if row['achievement_id'] is None:
                continue
            title_by_achievement.setdefault(int(row['achievement_id']), []).append(
                {
                    'id': int(row['id']),
                    'name': str(row['name']),
                    'original_name': str(row['original_name'] or ''),
                    'ability_desc': str(row['ability_desc'] or ''),
                }
            )
    for row in _rows(
        conn,
        'SELECT id, name, point, desc, is_hide FROM achievement',
    ):
        entity_id = int(row['id'])
        items.append(
            ContentItem(
                'achievement',
                entity_id,
                str(row['name']),
                entity_id,
                {
                    'point': int(row['point'] or 0),
                    'description': str(row['desc'] or ''),
                    'hidden': bool(row['is_hide']),
                    'titles': sorted(
                        title_by_achievement.get(entity_id, []),
                        key=lambda title: title['id'],
                    ),
                },
            )
        )

    skills_by_pet: dict[int, list[dict[str, Any]]] = {}
    if _has_table(conn, 'skillinpetorm') and _has_table(conn, 'skill'):
        for row in _rows(
            conn,
            """
        SELECT link.pet_id, link.learning_level, link.is_special, link.is_advanced,
               link.is_fifth, skill.id, skill.name, skill.power, skill.max_pp,
               skill.accuracy, skill.crit_rate, skill.priority, skill.must_hit,
               skill.atk_num, skill.info, skill.category_id, skill.type_id,
               skill.hide_effect_id, skill.advance_id
        FROM skillinpetorm AS link
        JOIN skill ON skill.id = link.skill_id
        ORDER BY link.pet_id, link.learning_level, skill.id
            """,
        ):
            skills_by_pet.setdefault(int(row['pet_id']), []).append(
                {
                    'id': int(row['id']),
                    'name': str(row['name']),
                    'power': int(row['power'] or 0),
                    'max_pp': int(row['max_pp'] or 0),
                    'accuracy': int(row['accuracy'] or 0),
                    'crit_rate': int(row['crit_rate'] or 0),
                    'priority': int(row['priority'] or 0),
                    'must_hit': bool(row['must_hit']),
                    'atk_num': int(row['atk_num'] or 0),
                    'info': str(row['info'] or ''),
                    'category_id': int(row['category_id'] or 0),
                    'type_id': int(row['type_id'] or 0),
                    'hide_effect_id': int(row['hide_effect_id'] or 0),
                    'advance_id': int(row['advance_id'] or 0),
                    'learning_level': int(row['learning_level'] or 0),
                    'is_special': bool(row['is_special']),
                    'is_advanced': bool(row['is_advanced']),
                    'is_fifth': bool(row['is_fifth']),
                }
            )

    soulmarks_by_pet: dict[int, list[dict[str, Any]]] = {}
    if _has_table(conn, 'pet_advance') and _has_table(conn, 'soulmark'):
        for row in _rows(
            conn,
            """
        SELECT advance.pet_id, soulmark.id, soulmark.desc,
               soulmark.desc_formatting_adjustment, soulmark.analyze_desc,
               soulmark.pve_effective, soulmark.intensified, soulmark.is_adv,
               soulmark.effect_in_use_id, soulmark.intensified_to_id
        FROM pet_advance AS advance
        JOIN soulmark ON soulmark.id = advance.soulmark_id
        ORDER BY advance.pet_id, soulmark.id
            """,
        ):
            soulmarks_by_pet.setdefault(int(row['pet_id']), []).append(
                {
                    'id': int(row['id']),
                    'desc': str(row['desc'] or ''),
                    'desc_formatting_adjustment': str(
                        row['desc_formatting_adjustment'] or ''
                    ),
                    'analyze_desc': str(row['analyze_desc'] or ''),
                    'pve_effective': bool(row['pve_effective']),
                    'intensified': bool(row['intensified']),
                    'is_adv': bool(row['is_adv']),
                    'effect_in_use_id': int(row['effect_in_use_id'] or 0),
                    'intensified_to_id': int(row['intensified_to_id'] or 0),
                }
            )

    statuses_by_pet: dict[int, list[dict[str, Any]]] = {}
    if _has_table(conn, 'special_effect_status'):
        for row in _rows(
            conn,
            """
            SELECT status_id, name, description, show_monster_id
            FROM special_effect_status
            WHERE show_monster_id IS NOT NULL
            ORDER BY show_monster_id, status_id
            """,
        ):
            statuses_by_pet.setdefault(int(row['show_monster_id']), []).append(
                {
                    'status_id': int(row['status_id']),
                    'name': str(row['name'] or ''),
                    'description': str(row['description'] or ''),
                }
            )

    pet_columns = (
        'yielding_exp',
        'catch_rate',
        'evolving_lv',
        'releaseable',
        'fusion_master',
        'fusion_sub',
        'has_resistance',
        'resource_id',
        'enemy_resource_id',
        'type_id',
        'gender_id',
        'pet_class_id',
        'base_stats_id',
        'yielding_ev_id',
        'vipbuff_id',
        'mount_type_id',
        'diy_stats_id',
        'peak_pool_id',
        'peak_expert_pool_id',
        'peak_pool_vote_id',
    )
    pet_columns = tuple(
        column for column in pet_columns if column in _table_columns(conn, 'pet')
    )
    pet_select = ', '.join(('id', 'name', *pet_columns))
    for row in _rows(conn, f'SELECT {pet_select} FROM pet'):
        entity_id = int(row['id'])
        items.append(
            ContentItem(
                'pet',
                entity_id,
                str(row['name']),
                entity_id,
                {
                    'stats': {column: int(row[column] or 0) for column in pet_columns},
                    'skills': skills_by_pet.get(entity_id, []),
                    'soulmarks': soulmarks_by_pet.get(entity_id, []),
                    'special_effect_statuses': statuses_by_pet.get(entity_id, []),
                },
            )
        )

    skin_fields = tuple(
        field
        for field in (
            'resource_id',
            'enemy_resource_id',
            'card_price',
            'pet_id',
            'category_id',
            'series_id',
            'sub_type_id',
        )
        if field in _table_columns(conn, 'pet_skin')
    )
    skin_select = ', '.join(
        ('skin.id', 'skin.name', *(f'skin.{field}' for field in skin_fields))
    )
    pet_join = (
        'LEFT JOIN pet ON pet.id = skin.pet_id' if 'pet_id' in skin_fields else ''
    )
    pet_name = ', pet.name AS pet_name' if pet_join else ", '' AS pet_name"
    for row in _rows(
        conn, f'SELECT {skin_select}{pet_name} FROM pet_skin AS skin {pet_join}'
    ):
        entity_id = int(row['id'])
        items.append(
            ContentItem(
                'pet_skin',
                entity_id,
                str(row['name']),
                entity_id,
                {
                    'pet_name': str(row['pet_name'] or ''),
                    **{field: int(row[field] or 0) for field in skin_fields},
                },
            )
        )

    for category, table, fields in (
        ('mintmark', 'mintmark', ('desc', 'type_id', 'rarity_id')),
        ('suit', 'suit', ('transform', 'tran_speed', 'suit_desc')),
    ):
        fields = tuple(
            field for field in fields if field in _table_columns(conn, table)
        )
        select = ', '.join(('id', 'name', *fields))
        for row in _rows(conn, f'SELECT {select} FROM {table}'):
            entity_id = int(row['id'])
            items.append(
                ContentItem(
                    category,
                    entity_id,
                    str(row['name']),
                    entity_id,
                    {field: row[field] for field in fields},
                )
            )

    equip_fields = tuple(
        field
        for field in (
            'speed',
            'part_type_id',
            'suit_id',
            'bonus_id',
            'occasion_id',
            'pk_hp',
            'pk_atk',
            'pk_fire_range',
        )
        if field in _table_columns(conn, 'equip')
    )
    equip_select = ', '.join(('id', 'name', *equip_fields))
    for row in _rows(conn, f'SELECT {equip_select} FROM equip'):
        part_type = int(row['part_type_id'] or 0) if 'part_type_id' in row.keys() else 0
        category = 'mount' if part_type == 6 else 'equip'
        entity_id = int(row['id'])
        items.append(
            ContentItem(
                category,
                entity_id,
                str(row['name']),
                entity_id,
                {field: int(row[field] or 0) for field in equip_fields},
            )
        )

    for category, table in (
        ('autocard_card', 'autocard_card'),
        ('autocard_role', 'autocard_role'),
    ):
        if not _has_table(conn, table):
            continue
        for row in _rows(conn, f'SELECT id, name, raw_json FROM {table}'):
            entity_id = int(row['id'])
            try:
                payload = json.loads(str(row['raw_json']))
            except json.JSONDecodeError:
                payload = {'raw_json': str(row['raw_json'])}
            items.append(
                ContentItem(
                    category,
                    entity_id,
                    str(row['name']),
                    entity_id,
                    payload if isinstance(payload, dict) else {'raw_json': payload},
                )
            )

    return tuple(sorted(items, key=lambda item: (item.category, item.entity_id)))


def _load_previous_state(path: Path | None) -> ReleaseState | None:
    if path is None or not path.is_file():
        return None
    with sqlite3.connect(path) as conn:
        version = _config_version(conn)
        if not _has_table(conn, RELEASE_TABLE):
            return ReleaseState(version, None, _weekly_cycle(version), False, ())
        row = conn.execute(
            f'SELECT current_git_sha, weekly_cycle, baseline_established FROM {RELEASE_TABLE} WHERE id = 1'
        ).fetchone()
        if row is None:
            return ReleaseState(version, None, _weekly_cycle(version), False, ())
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
        )


def _new_items(
    current: tuple[ContentItem, ...], previous: tuple[ContentItem, ...]
) -> tuple[ContentItem, ...]:
    previous_by_id = {(item.category, item.entity_id) for item in previous}
    previous_semantic = {item.semantic_key for item in previous}
    return tuple(
        item.with_change_kind('added')
        for item in current
        if (item.category, item.entity_id) not in previous_by_id
        and item.semantic_key not in previous_semantic
    )


def _modified_items(
    current: tuple[ContentItem, ...], previous: tuple[ContentItem, ...]
) -> tuple[ContentItem, ...]:
    previous_by_id = {(item.category, item.entity_id): item for item in previous}
    return tuple(
        item.with_change_kind('modified')
        for item in current
        if (previous_item := previous_by_id.get((item.category, item.entity_id)))
        is not None
        and item.semantic_key != previous_item.semantic_key
    )


def _current_subset(
    candidates: Iterable[ContentItem], current: tuple[ContentItem, ...]
) -> tuple[ContentItem, ...]:
    current_by_id = {(item.category, item.entity_id): item for item in current}
    return tuple(
        sorted(
            (
                replace(
                    current_by_id[(item.category, item.entity_id)],
                    change_kind=item.change_kind,
                )
                for item in candidates
                if (item.category, item.entity_id) in current_by_id
            ),
            key=lambda item: (item.category, item.entity_id),
        )
    )


def build_release_state(
    current_path: Path,
    previous_path: Path | None,
    current_git_sha: str,
) -> ReleaseState:
    with sqlite3.connect(current_path) as conn:
        current_version = _config_version(conn)
        current_items = load_current_items(conn)
    previous = _load_previous_state(previous_path)
    cycle = _weekly_cycle(current_version)
    if previous is None:
        return ReleaseState(current_version, current_git_sha, cycle, False, ())
    if previous.config_version == current_version:
        # A parser-only rebuild must not turn old rows into a new weekly update.
        return ReleaseState(
            current_version,
            current_git_sha,
            previous.weekly_cycle,
            previous.baseline_established,
            _current_subset(previous.items, current_items),
        )

    with sqlite3.connect(previous_path) as conn:
        previous_rows = load_current_items(conn)
    increment = (
        *_new_items(current_items, previous_rows),
        *_modified_items(current_items, previous_rows),
    )
    if previous.weekly_cycle == cycle and previous.baseline_established:
        items = _current_subset((*previous.items, *increment), current_items)
    else:
        items = increment
    return ReleaseState(current_version, current_git_sha, cycle, True, items)


def write_release_state(
    path: Path,
    state: ReleaseState,
    previous: ReleaseState | None,
) -> None:
    generated_at = datetime.now().astimezone().isoformat(timespec='seconds')
    with sqlite3.connect(path) as conn:
        conn.execute(f'DROP TABLE IF EXISTS {RELEASE_TABLE}')
        conn.execute(f'DROP TABLE IF EXISTS {ITEM_TABLE}')
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
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                state.config_version,
                previous.config_version if previous else None,
                state.git_sha or 'unknown',
                previous.git_sha if previous else None,
                state.weekly_cycle,
                generated_at,
                int(state.baseline_established),
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
        conn.execute(
            f'CREATE INDEX idx_{ITEM_TABLE}_category_sort ON {ITEM_TABLE} (category, sort_value)'
        )
        conn.commit()


def should_promote_previous(
    state: ReleaseState,
    previous: ReleaseState | None,
) -> bool:
    return bool(
        previous is not None
        and previous.config_version != state.config_version
        and previous.weekly_cycle != state.weekly_cycle
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--current-git-sha', required=True)
    parser.add_argument(
        '--github-output',
        type=Path,
        help='Optional GitHub Actions output file for release promotion metadata.',
    )
    args = parser.parse_args()

    previous = _load_previous_state(args.previous)
    state = build_release_state(args.current, args.previous, args.current_git_sha)
    write_release_state(args.current, state, previous)
    promote_previous = should_promote_previous(state, previous)
    if args.github_output is not None:
        with args.github_output.open('a', encoding='utf-8') as output:
            output.write(f'weekly_cycle={state.weekly_cycle}\n')
            output.write(
                f'baseline_established={str(state.baseline_established).lower()}\n'
            )
            output.write(f'promote_previous={str(promote_previous).lower()}\n')
            output.write(f'previous_available={str(previous is not None).lower()}\n')
    status = 'ready' if state.baseline_established else 'baseline-not-established'
    print(  # noqa: T201 - CLI status is required by the GitHub Actions log.
        'new-content index: '
        f'status={status} cycle={state.weekly_cycle} items={len(state.items)}'
    )


if __name__ == '__main__':
    main()
