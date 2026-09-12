#!/usr/bin/env python3
"""Validate and seal the final SQLite release after all post-processing."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import seerapi_models  # noqa: F401
from sqlmodel import SQLModel


SCHEMA_CONTRACT_VERSION = '1'
SCHEMA_CONTRACT_VERSION_KEY = 'ironsbot_schema_contract_version'
SCHEMA_TABLES_KEY = 'ironsbot_schema_tables'
SCHEMA_FINGERPRINT_KEY = 'ironsbot_schema_fingerprint'

# These tables are produced outside SQLModel: parsed ConfigPackage facts and
# post-build release indexes. Keep this list at the producer boundary so
# consumers do not duplicate the complete physical schema.
GENERATED_RELEASE_TABLES = frozenset(
    {
        'autocard_buff',
        'autocard_card',
        'autocard_nature',
        'autocard_role_raw',
        'autocard_season_effect',
        'buff',
        'buff_type',
        'effect_description',
        'field_effect',
        'field_effect_type',
        'flash_mount_image',
        'flash_mount_image_pending',
        'ironsbot_metadata',
        'item_exchange_price',
        'mintmark_quality',
        'new_content_category_state',
        'new_content_item',
        'new_content_release',
        'new_content_source_category',
        'new_content_source_snapshot',
        'peak_cost_pool',
        'pet_partner_group',
        'pet_partner_member',
        'pet_partner_upgrade',
        'sign',
        'sign_subitem',
        'skin_image_resolution',
        'skin_item_tip',
        'skin_shop_price',
        'skin_store_price',
        'soulmark_icon',
        'soulmark_icon_render_issue',
        'special_effect_status',
    }
)


def required_release_tables() -> frozenset[str]:
    """Return the complete producer-owned schema required by contract v1."""

    return frozenset(SQLModel.metadata.tables) | GENERATED_RELEASE_TABLES


def schema_fingerprint(
    connection: sqlite3.Connection,
    tables: tuple[str, ...],
) -> str:
    """Hash canonical DDL for declared tables and their secondary objects."""

    placeholders = ','.join('?' for _ in tables)
    rows = tuple(
        connection.execute(
            f"""
            SELECT type, name, tbl_name, COALESCE(sql, '')
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
              AND tbl_name IN ({placeholders})
              AND type IN ('table', 'index', 'trigger')
            ORDER BY type, name
            """,
            tables,
        )
    )
    payload = json.dumps(rows, separators=(',', ':'), ensure_ascii=False)
    return sha256(payload.encode()).hexdigest()


def finalize_release_contract(database: Path) -> tuple[str, ...]:
    """Validate a final release and persist its physical schema manifest."""

    if not database.is_file():
        raise FileNotFoundError(database)
    with sqlite3.connect(database) as connection:
        integrity = connection.execute('PRAGMA integrity_check').fetchone()
        if integrity != ('ok',):
            raise ValueError(f'SQLite integrity check failed: {integrity!r}')
        tables = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        )
        missing = sorted(required_release_tables() - set(tables))
        if missing:
            raise ValueError(f'release is missing required tables: {", ".join(missing)}')
        version = connection.execute(
            'SELECT value FROM ironsbot_metadata WHERE key = ?',
            (SCHEMA_CONTRACT_VERSION_KEY,),
        ).fetchone()
        if version != (SCHEMA_CONTRACT_VERSION,):
            actual = None if version is None else version[0]
            raise ValueError(
                'release schema contract version mismatch: '
                f'expected {SCHEMA_CONTRACT_VERSION!r}, got {actual!r}'
            )
        fingerprint = schema_fingerprint(connection, tables)
        metadata = (
            (SCHEMA_TABLES_KEY, json.dumps(tables, separators=(',', ':'))),
            (SCHEMA_FINGERPRINT_KEY, fingerprint),
        )
        connection.executemany(
            """
            INSERT INTO ironsbot_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            metadata,
        )
        connection.commit()
    return tables


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    args = parser.parse_args()
    tables = finalize_release_contract(args.database)
    with sqlite3.connect(args.database) as connection:
        fingerprint = schema_fingerprint(connection, tables)
    print(f'Final release contract validated: {len(tables)} tables, {fingerprint=}')


if __name__ == '__main__':
    main()
