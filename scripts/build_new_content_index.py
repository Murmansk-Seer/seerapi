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
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

RELEASE_TABLE = 'new_content_release'
ITEM_TABLE = 'new_content_item'
SOURCE_SNAPSHOT_TABLE = 'new_content_source_snapshot'
CATEGORY_SNAPSHOT_TABLE = 'new_content_source_category'
CATEGORY_STATE_TABLE = 'new_content_category_state'
AUTOCARD_SANCTUARY_EFFECT_CATEGORY = 'autocard_sanctuary_effect'
AUTOCARD_SANCTUARY_EFFECT_TABLE = 'autocard_season_effect'
PET_VOLATILE_STATS = frozenset(
    {
        'peak_pool_id',
        'peak_expert_pool_id',
        'peak_pool_vote_id',
    }
)
PET_SKILL_RELATION_FIELDS = (
    'id',
    'learning_level',
    'is_special',
    'is_advanced',
    'is_fifth',
)
SEMANTIC_SCHEMA_VERSION = 2
SEMANTIC_MIGRATION_CATEGORIES = frozenset({'pet', 'skill', 'equip', 'mount'})
SEMANTIC_MIGRATION_PRUNE_CATEGORIES = frozenset({'pet', 'equip', 'mount'})

CONTENT_CATEGORIES = (
    'achievement',
    'pet',
    'pet_skin',
    'skill',
    'mintmark',
    'suit',
    'equip',
    'mount',
    'autocard_card',
    'autocard_role',
    AUTOCARD_SANCTUARY_EFFECT_CATEGORY,
)

CATEGORY_SOURCE_TABLES: dict[str, tuple[str, ...]] = {
    'achievement': ('achievement',),
    'pet': ('pet',),
    'pet_skin': ('pet_skin',),
    'skill': ('skill',),
    'mintmark': ('mintmark',),
    'suit': ('suit',),
    'equip': ('equip',),
    'mount': ('equip',),
    'autocard_card': ('autocard_card',),
    'autocard_role': ('autocard_role',),
    AUTOCARD_SANCTUARY_EFFECT_CATEGORY: (AUTOCARD_SANCTUARY_EFFECT_TABLE,),
}


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
        payload = dict(self.payload)
        if self.category == 'pet_skin':
            # The linked pet name is presentation-only. A pet change must not
            # make every one of its skins look modified.
            payload = {
                key: value for key, value in payload.items() if key != 'pet_name'
            }
        elif self.category == 'pet':
            # Weekly peak-pool membership is operational rotation state, not a
            # change to the pet itself. Skill definitions are indexed in the
            # skill category; retain only the pet-to-skill relationship here so
            # a corrected skill description does not modify every linked pet.
            if isinstance(stats := payload.get('stats'), dict):
                payload['stats'] = {
                    key: value
                    for key, value in stats.items()
                    if key not in PET_VOLATILE_STATS
                }
            if isinstance(skills := payload.get('skills'), list):
                payload['skills'] = [
                    {
                        field: skill[field]
                        for field in PET_SKILL_RELATION_FIELDS
                        if field in skill
                    }
                    for skill in skills
                    if isinstance(skill, dict)
                ]
        elif self.category == 'skill':
            # A new pet learning an existing skill changes the pet relation,
            # not the skill definition.
            payload.pop('pets', None)
        return json.dumps(
            {
                'category': self.category,
                'name': self.name,
                'payload': payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    @property
    def semantic_digest(self) -> str:
        return hashlib.sha256(self.semantic_key.encode('utf-8')).hexdigest()

    def with_change_kind(self, change_kind: str) -> 'ContentItem':
        return replace(self, change_kind=change_kind)


@dataclass(frozen=True)
class ReleaseState:
    config_version: str
    git_sha: str | None
    weekly_cycle: str
    baseline_established: bool
    items: tuple[ContentItem, ...]
    source_items: tuple['SourceSnapshotItem', ...] = field(default_factory=tuple)
    source_categories: frozenset[str] = field(default_factory=frozenset)
    category_states: tuple['CategoryState', ...] = field(default_factory=tuple)
    semantic_schema_version: int = SEMANTIC_SCHEMA_VERSION


@dataclass(frozen=True)
class SourceSnapshotItem:
    category: str
    entity_id: int
    semantic_digest: str

    @classmethod
    def from_content(cls, item: ContentItem) -> 'SourceSnapshotItem':
        return cls(item.category, item.entity_id, item.semantic_digest)


@dataclass(frozen=True)
class CategoryState:
    category: str
    comparison_ready: bool
    reason: str


@dataclass(frozen=True)
class SourceHistoryAddition:
    """An entity added by the source repository between two published revisions."""

    category: str
    entity_id: int


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


def _equip_bonus_payloads(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    """Resolve auto-numbered bonus rows into stable, meaningful content."""

    if not _has_table(conn, 'equip_bonus'):
        return {}

    attributes: dict[int, dict[str, Any]] = {}
    if _has_table(conn, 'equip_bonus_attr'):
        attributes = {
            int(row['id']): {key: row[key] for key in row.keys() if key != 'id'}
            for row in _rows(conn, 'SELECT * FROM equip_bonus_attr')
        }

    effects: dict[int, dict[str, Any]] = {}
    if _has_table(conn, 'eid_effect_in_use'):
        for row in _rows(conn, 'SELECT * FROM eid_effect_in_use'):
            payload = {key: row[key] for key in row.keys() if key != 'id'}
            if isinstance(effect_args := payload.get('effect_args'), str):
                try:
                    payload['effect_args'] = json.loads(effect_args)
                except json.JSONDecodeError:
                    pass
            effects[int(row['id'])] = payload

    result: dict[int, dict[str, Any]] = {}
    for row in _rows(conn, 'SELECT * FROM equip_bonus'):
        payload = {
            key: row[key]
            for key in row.keys()
            if key not in {'id', 'attribute_id', 'effect_in_use_id'}
        }
        if row['attribute_id'] is not None:
            payload['attribute'] = attributes.get(int(row['attribute_id']), {})
        if row['effect_in_use_id'] is not None:
            payload['effect'] = effects.get(int(row['effect_in_use_id']), {})
        result[int(row['id'])] = payload
    return result


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
    pets_by_skill: dict[int, list[dict[str, Any]]] = {}
    if _has_table(conn, 'skillinpetorm') and _has_table(conn, 'skill'):
        for row in _rows(
            conn,
            """
        SELECT link.pet_id, link.learning_level, link.is_special, link.is_advanced,
               link.is_fifth, skill.id, skill.name, skill.power, skill.max_pp,
               skill.accuracy, skill.crit_rate, skill.priority, skill.must_hit,
               skill.atk_num, skill.info, skill.category_id, skill.type_id,
               skill.hide_effect_id, skill.advance_id,
               COALESCE(pet.name, '') AS pet_name
        FROM skillinpetorm AS link
        JOIN skill ON skill.id = link.skill_id
        LEFT JOIN pet ON pet.id = link.pet_id
        ORDER BY link.pet_id, link.learning_level, skill.id
            """,
        ):
            skill = {
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
            skills_by_pet.setdefault(int(row['pet_id']), []).append(skill)
            pets_by_skill.setdefault(int(row['id']), []).append(
                {
                    'id': int(row['pet_id']),
                    'name': str(row['pet_name'] or ''),
                    'learning_level': skill['learning_level'],
                    'is_special': skill['is_special'],
                    'is_advanced': skill['is_advanced'],
                    'is_fifth': skill['is_fifth'],
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

    if _has_table(conn, 'skill'):
        skill_fields = tuple(
            field
            for field in (
                'power',
                'max_pp',
                'accuracy',
                'crit_rate',
                'priority',
                'must_hit',
                'atk_num',
                'info',
                'category_id',
                'type_id',
                'hide_effect_id',
                'advance_id',
            )
            if field in _table_columns(conn, 'skill')
        )
        skill_select = ', '.join(('id', 'name', *skill_fields))
        for row in _rows(conn, f'SELECT {skill_select} FROM skill'):
            entity_id = int(row['id'])
            payload: dict[str, Any] = {
                'pets': pets_by_skill.get(entity_id, []),
            }
            for field in skill_fields:
                if field == 'info':
                    payload[field] = str(row[field] or '')
                elif field == 'must_hit':
                    payload[field] = bool(row[field])
                else:
                    payload[field] = int(row[field] or 0)
            items.append(
                ContentItem(
                    'skill',
                    entity_id,
                    str(row['name']),
                    entity_id,
                    payload,
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
    equip_bonus_payloads = _equip_bonus_payloads(conn)
    equip_select = ', '.join(('id', 'name', *equip_fields))
    for row in _rows(conn, f'SELECT {equip_select} FROM equip'):
        part_type = int(row['part_type_id'] or 0) if 'part_type_id' in row.keys() else 0
        category = 'mount' if part_type == 6 else 'equip'
        entity_id = int(row['id'])
        payload = {
            field: int(row[field] or 0)
            for field in equip_fields
            if field != 'bonus_id'
        }
        if 'bonus_id' in row.keys() and row['bonus_id'] is not None:
            payload['bonus'] = equip_bonus_payloads.get(int(row['bonus_id']), {})
        items.append(
            ContentItem(
                category,
                entity_id,
                str(row['name']),
                entity_id,
                payload,
            )
        )

    if _has_table(conn, 'autocard_card'):
        for row in _rows(conn, 'SELECT id, name, raw_json FROM autocard_card'):
            entity_id = int(row['id'])
            try:
                payload = json.loads(str(row['raw_json']))
            except json.JSONDecodeError:
                payload = {'raw_json': str(row['raw_json'])}
            items.append(
                ContentItem(
                    'autocard_card',
                    entity_id,
                    str(row['name']),
                    entity_id,
                    payload if isinstance(payload, dict) else {'raw_json': payload},
                )
            )

    if _has_table(conn, 'autocard_role'):
        if _has_table(conn, 'autocard_role_raw'):
            role_query = '''
                SELECT role.id, role.name, raw.raw_json
                FROM autocard_role AS role
                JOIN autocard_role_raw AS raw ON raw.role_id = role.id
                ORDER BY role.id
            '''
        elif 'raw_json' in _table_columns(conn, 'autocard_role'):
            role_query = 'SELECT id, name, raw_json FROM autocard_role ORDER BY id'
        else:
            role_query = None
        for row in _rows(conn, role_query) if role_query is not None else ():
            entity_id = int(row['id'])
            try:
                payload = json.loads(str(row['raw_json']))
            except json.JSONDecodeError:
                payload = {'raw_json': str(row['raw_json'])}
            items.append(
                ContentItem(
                    'autocard_role',
                    entity_id,
                    str(row['name']),
                    entity_id,
                    payload if isinstance(payload, dict) else {'raw_json': payload},
                )
            )

    if _has_table(conn, AUTOCARD_SANCTUARY_EFFECT_TABLE):
        for row in _rows(
            conn,
            f'''
            SELECT
                effect.id,
                effect.sanctuary_id,
                effect.name,
                effect.description,
                effect.buff_id,
                effect.buff_param,
                effect.count_buff_id,
                effect.count_type,
                effect.count_num,
                effect.unlock_round,
                effect.pic_id,
                effect.season_id,
                effect.stage,
                COALESCE(base.name, '') AS sanctuary_name,
                COALESCE(base.pic_id, 0) AS sanctuary_pet_id,
                COALESCE(pet.name, '') AS sanctuary_pet_name
            FROM {AUTOCARD_SANCTUARY_EFFECT_TABLE} AS effect
            LEFT JOIN {AUTOCARD_SANCTUARY_EFFECT_TABLE} AS base
                ON base.sanctuary_id = effect.sanctuary_id
               AND base.unlock_round = 0
               AND base.pic_id > 0
            LEFT JOIN pet
                ON pet.id = base.pic_id
            ORDER BY effect.sanctuary_id, effect.unlock_round, effect.stage, effect.id
            ''',
        ):
            entity_id = int(row['id'])
            items.append(
                ContentItem(
                    AUTOCARD_SANCTUARY_EFFECT_CATEGORY,
                    entity_id,
                    str(row['name']),
                    entity_id,
                    {
                        'sanctuary_id': int(row['sanctuary_id']),
                        'sanctuary_name': str(row['sanctuary_name'] or ''),
                        'sanctuary_pet_id': int(row['sanctuary_pet_id'] or 0),
                        'sanctuary_pet_name': str(row['sanctuary_pet_name'] or ''),
                        'description': str(row['description'] or ''),
                        'buff_id': str(row['buff_id'] or ''),
                        'buff_param': str(row['buff_param'] or ''),
                        'count_buff_id': str(row['count_buff_id'] or ''),
                        'count_type': int(row['count_type'] or 0),
                        'count_num': int(row['count_num'] or 0),
                        'unlock_round': int(row['unlock_round'] or 0),
                        'pic_id': int(row['pic_id'] or 0),
                        'season_id': int(row['season_id'] or 0),
                        'stage': int(row['stage'] or 0),
                    },
                )
            )

    return tuple(sorted(items, key=lambda item: (item.category, item.entity_id)))


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
                source_items = (
                    *(
                        item
                        for item in source_items
                        if item.category not in SEMANTIC_MIGRATION_CATEGORIES
                    ),
                    *(
                        SourceSnapshotItem.from_content(item)
                        for item in current_items
                        if item.category in SEMANTIC_MIGRATION_CATEGORIES
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
                replace(
                    current_by_id[key],
                    change_kind=change_kind,
                )
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
            carried_items = tuple(
                item
                for item in carried_items
                if not (
                    item.change_kind == 'modified'
                    and item.category in SEMANTIC_MIGRATION_PRUNE_CATEGORIES
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
