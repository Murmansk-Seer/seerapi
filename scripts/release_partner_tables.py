# SPDX-License-Identifier: MIT
"""SQLite writer for official contract-partner release tables."""

from __future__ import annotations

import sqlite3

if __package__:
    from .partner_contract_sources import PetPartnerData
else:
    from partner_contract_sources import (
        PetPartnerData,  # type: ignore[import-not-found]
    )


PET_PARTNER_GROUP_TABLE = "pet_partner_group"
PET_PARTNER_MEMBER_TABLE = "pet_partner_member"
PET_PARTNER_UPGRADE_TABLE = "pet_partner_upgrade"
PET_PARTNER_UPGRADE_NORMALIZED_SOURCE = (
    "ConfigPackage/partnerEffectUpgrade.bytes#normalized-v1"
)


def replace_pet_partner_tables(
    conn: sqlite3.Connection,
    data: PetPartnerData,
    *,
    updated_at: float,
) -> None:
    """Replace contract-partner tables derived from official game config."""
    conn.execute(f"DROP TABLE IF EXISTS {PET_PARTNER_UPGRADE_TABLE}")
    conn.execute(f"DROP TABLE IF EXISTS {PET_PARTNER_MEMBER_TABLE}")
    conn.execute(f"DROP TABLE IF EXISTS {PET_PARTNER_GROUP_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {PET_PARTNER_GROUP_TABLE} (
            group_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            cost_item_id INTEGER NOT NULL,
            cost_item_name TEXT NOT NULL,
            cost_item_quantity INTEGER NOT NULL,
            required_pet_count INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE {PET_PARTNER_MEMBER_TABLE} (
            group_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            display_order INTEGER NOT NULL,
            PRIMARY KEY (group_id, pet_id)
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE {PET_PARTNER_UPGRADE_TABLE} (
            pet_id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            before_description TEXT NOT NULL,
            after_description TEXT NOT NULL,
            skill_id INTEGER,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {PET_PARTNER_GROUP_TABLE}
            (
                group_id, name, cost_item_id, cost_item_name, cost_item_quantity,
                required_pet_count, source, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                group.group_id,
                group.name,
                group.cost_item_id,
                group.cost_item_name,
                group.cost_item_quantity,
                len(group.member_pet_ids),
                "ConfigPackage/partner.bytes",
                updated_at,
            )
            for group in data.groups
        ],
    )
    conn.executemany(
        f"""
        INSERT INTO {PET_PARTNER_MEMBER_TABLE}
            (group_id, pet_id, display_order)
        VALUES (?, ?, ?)
        """,
        [
            (group.group_id, pet_id, display_order)
            for group in data.groups
            for display_order, pet_id in enumerate(group.member_pet_ids, start=1)
        ],
    )
    group_id_by_pet = {
        pet_id: group.group_id
        for group in data.groups
        for pet_id in group.member_pet_ids
    }
    conn.executemany(
        f"""
        INSERT INTO {PET_PARTNER_UPGRADE_TABLE}
            (
                pet_id, group_id, before_description, after_description, skill_id,
                source, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                upgrade.pet_id,
                group_id_by_pet[upgrade.pet_id],
                upgrade.before_description,
                upgrade.after_description,
                upgrade.skill_id,
                PET_PARTNER_UPGRADE_NORMALIZED_SOURCE,
                updated_at,
            )
            for upgrade in data.upgrades
            if upgrade.pet_id in group_id_by_pet
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX idx_{PET_PARTNER_MEMBER_TABLE}_pet_id
        ON {PET_PARTNER_MEMBER_TABLE} (pet_id)
        """
    )
    conn.execute(
        f"""
        CREATE INDEX idx_{PET_PARTNER_UPGRADE_TABLE}_group_id
        ON {PET_PARTNER_UPGRADE_TABLE} (group_id)
        """
    )
