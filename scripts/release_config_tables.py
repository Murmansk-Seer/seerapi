# SPDX-License-Identifier: MIT
"""SQLite writer for ConfigPackage-derived release tables.

The release builder owns source download and transaction ordering. This module
only replaces tables whose rows are already decoded from ConfigPackage or
official pet-image probes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
import sqlite3
from typing import Protocol

MINTMARK_QUALITY_TABLE = 'mintmark_quality'
SKIN_STORE_PRICE_TABLE = 'skin_store_price'
SKIN_SHOP_PRICE_TABLE = 'skin_shop_price'
SKIN_ITEM_TIP_TABLE = 'skin_item_tip'
SKIN_IMAGE_RESOLUTION_TABLE = 'skin_image_resolution'
SKIN_TICKET_RULE_TABLE = 'skin_ticket_rule'


def replace_skin_ticket_rules(conn: sqlite3.Connection) -> int:
    """Publish only explicit, unconditional per-ticket diamond deductions.

    This recognized complete item-description grammar is deliberately narrow.
    Other numbers, ticket types, shop prices, and conditional text are not
    evidence of a per-ticket deduction.
    """
    rows = []
    for item_id, name, description in conn.execute(
        'SELECT DISTINCT item.id, item.name, item.desc FROM item '
        'JOIN skin_store_price ON skin_store_price.ticket_id = item.id '
        'ORDER BY item.id'
    ):
        if not name or not description:
            continue
        match = re.fullmatch(
            r'通过“[^”\r\n]+”获得，可在幸运橱窗中使用，每张'
            + re.escape(name)
            + r'可抵扣([1-9][0-9]*)钻石。',
            description,
        )
        if match is None:
            continue
        value = int(match[1])
        if value > 9223372036854775807:
            continue
        rows.append(
            (
                item_id,
                value,
                'item.desc:lucky_window_per_ticket_diamonds_v1',
                description,
            )
        )
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {SKIN_TICKET_RULE_TABLE} (
            ticket_id INTEGER PRIMARY KEY,
            diamonds_per_ticket INTEGER NOT NULL CHECK (diamonds_per_ticket > 0),
            source TEXT NOT NULL,
            source_text TEXT NOT NULL
        )
    """)
    conn.execute(f'DELETE FROM {SKIN_TICKET_RULE_TABLE}')
    conn.executemany(
        f'INSERT INTO {SKIN_TICKET_RULE_TABLE} '
        '(ticket_id, diamonds_per_ticket, source, source_text) VALUES (?, ?, ?, ?)',
        rows,
    )
    return len(rows)


class _SkinStorePrice(Protocol):
    @property
    def skin_id(self) -> int: ...
    @property
    def pool_id(self) -> int: ...
    @property
    def price(self) -> int: ...
    @property
    def original_price(self) -> int: ...
    @property
    def discount_rate(self) -> int: ...
    @property
    def selected_price(self) -> int: ...
    @property
    def ticket_id(self) -> int: ...
    @property
    def ticket_num(self) -> int: ...
    @property
    def start_time(self) -> int: ...
    @property
    def end_time(self) -> int: ...


class _SkinShopPrice(Protocol):
    @property
    def skin_id(self) -> int: ...
    @property
    def resource_id(self) -> int: ...
    @property
    def card_price(self) -> int: ...
    @property
    def diamond_price(self) -> int: ...
    @property
    def original_price(self) -> int: ...


class ConfigPackageTableData(Protocol):
    @property
    def mintmark_quality(self) -> Mapping[int, int]: ...
    @property
    def skin_store_prices(self) -> Sequence[_SkinStorePrice]: ...
    @property
    def skin_shop_prices(self) -> Sequence[_SkinShopPrice]: ...
    @property
    def skin_item_tips(self) -> Mapping[int, str]: ...


class SkinImageResolutionRecord(Protocol):
    @property
    def skin_id(self) -> int: ...
    @property
    def head_resource_id(self) -> int: ...
    @property
    def body_resource_id(self) -> int: ...
    @property
    def head_resolution(self) -> str: ...
    @property
    def body_resolution(self) -> str: ...
    @property
    def source_pet_id(self) -> int | None: ...


def replace_config_package_tables(
    conn: sqlite3.Connection,
    config_data: ConfigPackageTableData,
    skin_image_resolutions: Sequence[SkinImageResolutionRecord],
    *,
    now: float,
) -> None:
    """Replace ConfigPackage and official image-resolution release tables."""
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MINTMARK_QUALITY_TABLE} (
            mintmark_id INTEGER PRIMARY KEY,
            quality INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f'DELETE FROM {MINTMARK_QUALITY_TABLE}')
    conn.executemany(
        f"""
        INSERT INTO {MINTMARK_QUALITY_TABLE}
            (mintmark_id, quality, source, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        [
            (mintmark_id, quality, 'ConfigPackage/mintmark.bytes', now)
            for mintmark_id, quality in sorted(config_data.mintmark_quality.items())
        ],
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SKIN_STORE_PRICE_TABLE} (
            row_index INTEGER PRIMARY KEY,
            skin_id INTEGER NOT NULL,
            pool_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            original_price INTEGER NOT NULL,
            discount_rate INTEGER NOT NULL,
            selected_price INTEGER NOT NULL,
            ticket_id INTEGER NOT NULL,
            ticket_num INTEGER NOT NULL,
            start_time INTEGER NOT NULL,
            end_time INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f'DELETE FROM {SKIN_STORE_PRICE_TABLE}')
    conn.executemany(
        f"""
        INSERT INTO {SKIN_STORE_PRICE_TABLE}
            (
                row_index, skin_id, pool_id, price, original_price, discount_rate,
                selected_price, ticket_id, ticket_num, start_time, end_time, source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                index,
                item.skin_id,
                item.pool_id,
                item.price,
                item.original_price,
                item.discount_rate,
                item.selected_price,
                item.ticket_id,
                item.ticket_num,
                item.start_time,
                item.end_time,
                'ConfigPackage/skinStorePool.bytes',
                now,
            )
            for index, item in enumerate(config_data.skin_store_prices, start=1)
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{SKIN_STORE_PRICE_TABLE}_skin_id
        ON {SKIN_STORE_PRICE_TABLE} (skin_id)
        """
    )
    replace_skin_ticket_rules(conn)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SKIN_SHOP_PRICE_TABLE} (
            skin_id INTEGER PRIMARY KEY,
            resource_id INTEGER NOT NULL,
            card_price INTEGER NOT NULL,
            diamond_price INTEGER NOT NULL,
            original_price INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f'DELETE FROM {SKIN_SHOP_PRICE_TABLE}')
    conn.executemany(
        f"""
        INSERT INTO {SKIN_SHOP_PRICE_TABLE}
            (
                skin_id, resource_id, card_price, diamond_price, original_price,
                source, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.skin_id,
                item.resource_id,
                item.card_price,
                item.diamond_price,
                item.original_price,
                'ConfigPackage/skin_shop.bytes',
                now,
            )
            for item in config_data.skin_shop_prices
        ],
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SKIN_ITEM_TIP_TABLE} (
            item_id INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f'DELETE FROM {SKIN_ITEM_TIP_TABLE}')
    conn.executemany(
        f"""
        INSERT INTO {SKIN_ITEM_TIP_TABLE}
            (item_id, description, source, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        [
            (item_id, description, 'ConfigPackage/itemsTip.bytes', now)
            for item_id, description in sorted(config_data.skin_item_tips.items())
        ],
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SKIN_IMAGE_RESOLUTION_TABLE} (
            skin_id INTEGER PRIMARY KEY,
            head_resource_id INTEGER NOT NULL,
            body_resource_id INTEGER NOT NULL,
            head_resolution TEXT NOT NULL,
            body_resolution TEXT NOT NULL,
            source_pet_id INTEGER,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f'DELETE FROM {SKIN_IMAGE_RESOLUTION_TABLE}')
    conn.executemany(
        f"""
        INSERT INTO {SKIN_IMAGE_RESOLUTION_TABLE}
            (
                skin_id, head_resource_id, body_resource_id, head_resolution,
                body_resolution, source_pet_id, source, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                resolution.skin_id,
                resolution.head_resource_id,
                resolution.body_resource_id,
                resolution.head_resolution,
                resolution.body_resolution,
                resolution.source_pet_id,
                'official pet image assets',
                now,
            )
            for resolution in skin_image_resolutions
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{SKIN_IMAGE_RESOLUTION_TABLE}_source_pet_id
        ON {SKIN_IMAGE_RESOLUTION_TABLE} (source_pet_id)
        """
    )
