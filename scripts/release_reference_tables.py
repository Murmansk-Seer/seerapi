# SPDX-License-Identifier: MIT
"""SQLite writer for official reference-data release tables."""

from __future__ import annotations

from collections.abc import Iterable
import sqlite3
from typing import Protocol

ITEM_EXCHANGE_PRICE_TABLE = "item_exchange_price"
EFFECT_DESCRIPTION_TABLE = "effect_description"
SPECIAL_EFFECT_STATUS_TABLE = "special_effect_status"
PEAK_MASTER_POOL_VIEW = "peak_master_pool"


class ItemExchangePriceRecord(Protocol):
    source_key: str
    source_name: str
    source_entry_id: int
    item_id: int
    item_name: str
    item_quantity: int
    currency_item_id: int
    currency_name: str
    amount: int
    purchase_limit: int | None
    start_time: int
    end_time: int


class EffectDescriptionRecord(Protocol):
    effect_id: int
    name: str
    description: str


class SpecialEffectStatusRecord(Protocol):
    status_id: int
    name: str
    description: str
    show_monster_id: int


def replace_reference_tables(
    conn: sqlite3.Connection,
    *,
    item_exchange_prices: Iterable[ItemExchangePriceRecord],
    effect_descriptions: Iterable[EffectDescriptionRecord],
    special_effect_statuses: Iterable[SpecialEffectStatusRecord],
    now: float,
) -> None:
    """Replace parsed official shop and special-effect reference tables."""
    conn.execute(f"DROP TABLE IF EXISTS {ITEM_EXCHANGE_PRICE_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {ITEM_EXCHANGE_PRICE_TABLE} (
            source_key TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_entry_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            item_quantity INTEGER NOT NULL,
            currency_item_id INTEGER NOT NULL,
            currency_name TEXT NOT NULL,
            amount INTEGER NOT NULL,
            purchase_limit INTEGER,
            start_time INTEGER NOT NULL,
            end_time INTEGER NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (source_key, source_entry_id)
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {ITEM_EXCHANGE_PRICE_TABLE}
            (
                source_key, source_name, source_entry_id, item_id, item_name,
                item_quantity, currency_item_id, currency_name, amount,
                purchase_limit, start_time, end_time, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.source_key,
                item.source_name,
                item.source_entry_id,
                item.item_id,
                item.item_name,
                item.item_quantity,
                item.currency_item_id,
                item.currency_name,
                item.amount,
                item.purchase_limit,
                item.start_time,
                item.end_time,
                now,
            )
            for item in item_exchange_prices
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{ITEM_EXCHANGE_PRICE_TABLE}_item_id
        ON {ITEM_EXCHANGE_PRICE_TABLE} (item_id)
        """
    )
    conn.execute(f"DROP TABLE IF EXISTS {EFFECT_DESCRIPTION_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {EFFECT_DESCRIPTION_TABLE} (
            effect_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {EFFECT_DESCRIPTION_TABLE}
            (effect_id, name, description, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        [
            (effect.effect_id, effect.name, effect.description, now)
            for effect in effect_descriptions
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{EFFECT_DESCRIPTION_TABLE}_name
        ON {EFFECT_DESCRIPTION_TABLE} (name)
        """
    )
    conn.execute(f"DROP TABLE IF EXISTS {SPECIAL_EFFECT_STATUS_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {SPECIAL_EFFECT_STATUS_TABLE} (
            status_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            show_monster_id INTEGER NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (status_id, name)
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {SPECIAL_EFFECT_STATUS_TABLE}
            (status_id, name, description, show_monster_id, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                status.status_id,
                status.name,
                status.description,
                status.show_monster_id,
                now,
            )
            for status in special_effect_statuses
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX idx_{SPECIAL_EFFECT_STATUS_TABLE}_name
        ON {SPECIAL_EFFECT_STATUS_TABLE} (name)
        """
    )


def replace_peak_master_pool_projection(conn: sqlite3.Connection) -> None:
    """Expose normalized master-pool facts to the deployed IronsBot query."""

    existing = conn.execute(
        "SELECT type FROM sqlite_master WHERE name = ?",
        (PEAK_MASTER_POOL_VIEW,),
    ).fetchone()
    if existing is not None:
        object_type = str(existing[0])
        if object_type not in {'table', 'view'}:
            raise ValueError(f'unsupported {PEAK_MASTER_POOL_VIEW} object: {object_type}')
        conn.execute(f'DROP {object_type.upper()} {PEAK_MASTER_POOL_VIEW}')
    conn.execute(
        f"""
        CREATE VIEW {PEAK_MASTER_POOL_VIEW} AS
        SELECT
            pool.id AS id,
            pool.cost AS cost,
            pool.name AS name,
            (
                SELECT json_group_array(member.id)
                FROM (
                    SELECT pet.id
                    FROM pet
                    WHERE pet.peak_cost_pool_id = pool.id
                    ORDER BY pet.id
                ) AS member
            ) AS pet_ids_json,
            CAST(strftime('%m', pool.start_time) AS INTEGER) AS subkey_month,
            CAST(strftime('%Y%m%d', pool.start_time) AS INTEGER) AS subkey_total,
            strftime('%Y_%m_%d %H:%M:%S', pool.end_time) AS configured_time
        FROM peak_cost_pool AS pool
        """
    )
