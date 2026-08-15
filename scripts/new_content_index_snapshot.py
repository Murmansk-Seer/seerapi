"""Read the current SeerAPI SQLite snapshot into normalized content items."""

from __future__ import annotations

from collections.abc import Iterable
import json
import sqlite3
from typing import Any

from new_content_index_models import (
    AUTOCARD_SANCTUARY_EFFECT_CATEGORY,
    AUTOCARD_SANCTUARY_EFFECT_TABLE,
    ContentItem,
)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info({table})')}


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

    mintmark_quality_by_id: dict[int, int] = {}
    if _has_table(conn, 'mintmark_quality'):
        mintmark_quality_by_id = {
            int(row['mintmark_id']): int(row['quality'] or 0)
            for row in _rows(
                conn,
                'SELECT mintmark_id, quality FROM mintmark_quality',
            )
        }

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
            payload = {field: row[field] for field in fields}
            if category == 'mintmark':
                # Quality is extracted from the official Unity
                # ConfigPackage.  It intentionally remains separate from the
                # legacy primary-table rarity classification.
                payload['quality'] = mintmark_quality_by_id.get(entity_id, 0)
            items.append(
                ContentItem(
                    category,
                    entity_id,
                    str(row['name']),
                    entity_id,
                    payload,
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
        for row in _rows(
            conn,
            '''
            SELECT role.id, role.name, raw.raw_json
            FROM autocard_role AS role
            JOIN autocard_role_raw AS raw ON raw.role_id = role.id
            ORDER BY role.id
            ''',
        ):
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


