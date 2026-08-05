"""Publish deterministic soulmark display facts and explicit corrections."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import sqlite3


@dataclass(frozen=True, slots=True)
class SoulmarkDisplayAddition:
    """A build-time display fact for a soulmark absent from raw source data."""

    pet_id: int
    display_id: int
    description: str
    intensified: bool
    is_adv: bool
    pve_effective: bool | None
    tags: tuple[str, ...]
    display_order: int
    source: str
    analyze_description: str | None = None
    formatting_adjustment: str | None = None
    intensified_to_id: int | None = None


@dataclass(frozen=True, slots=True)
class SoulmarkDisplayBuildSummary:
    """Published row counts for raw display order and explicit additions."""

    display_rows: int
    addition_rows: int


# The legacy runtime branch for pet 2500 represented an official visible
# soulmark effect which is absent from the raw package.  Publishing it here
# makes the correction auditable and lets every renderer consume one snapshot.
SOULMARK_DISPLAY_ADDITIONS = (
    SoulmarkDisplayAddition(
        pet_id=2500,
        display_id=0,
        description="登场首回合所有攻击先制+1同时增加20%暴击率",
        intensified=True,
        is_adv=False,
        pve_effective=None,
        tags=(),
        display_order=0,
        source="seerapi/soulmark-display-corrections#pet-2500-v1",
    ),
)


def replace_pet_soulmark_display_facts(
    connection: sqlite3.Connection,
    *,
    now: float,
) -> SoulmarkDisplayBuildSummary:
    """Replace raw display order and declared additions for one data release."""
    rows_by_pet: dict[int, list[tuple[int, bool, bool, int | None]]] = defaultdict(list)
    for pet_id, soulmark_id, intensified, is_adv, intensified_to_id in connection.execute(
        """
        SELECT link.pet_id, soulmark.id, soulmark.intensified, soulmark.is_adv,
               soulmark.intensified_to_id
        FROM petsoulmarklink AS link
        JOIN soulmark ON soulmark.id = link.soulmark_id
        ORDER BY link.pet_id, soulmark.id
        """
    ):
        rows_by_pet[int(pet_id)].append(
            (int(soulmark_id), bool(intensified), bool(is_adv), intensified_to_id)
        )

    display_rows = _display_rows(rows_by_pet, now)
    connection.executescript(
        """
        DROP TABLE IF EXISTS pet_soulmark_display;
        CREATE TABLE pet_soulmark_display (
            pet_id INTEGER NOT NULL,
            soulmark_id INTEGER NOT NULL,
            root_soulmark_id INTEGER NOT NULL,
            display_order INTEGER NOT NULL,
            display_kind TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (pet_id, soulmark_id)
        );
        CREATE INDEX idx_pet_soulmark_display_order
        ON pet_soulmark_display (pet_id, display_order);

        DROP TABLE IF EXISTS pet_soulmark_display_addition;
        CREATE TABLE pet_soulmark_display_addition (
            pet_id INTEGER NOT NULL,
            display_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            analyze_description TEXT,
            formatting_adjustment TEXT,
            intensified INTEGER NOT NULL,
            intensified_to_id INTEGER,
            is_adv INTEGER NOT NULL,
            pve_effective INTEGER,
            tags_json TEXT NOT NULL,
            display_order INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (pet_id, display_id)
        );
        CREATE INDEX idx_pet_soulmark_display_addition_order
        ON pet_soulmark_display_addition (pet_id, display_order, display_id);
        """
    )
    connection.executemany(
        """
        INSERT INTO pet_soulmark_display
            (pet_id, soulmark_id, root_soulmark_id, display_order, display_kind, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        display_rows,
    )
    connection.executemany(
        """
        INSERT INTO pet_soulmark_display_addition
            (
                pet_id, display_id, description, analyze_description,
                formatting_adjustment, intensified, intensified_to_id, is_adv,
                pve_effective, tags_json, display_order, source, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                addition.pet_id,
                addition.display_id,
                addition.description,
                addition.analyze_description,
                addition.formatting_adjustment,
                int(addition.intensified),
                addition.intensified_to_id,
                int(addition.is_adv),
                (
                    int(addition.pve_effective)
                    if addition.pve_effective is not None
                    else None
                ),
                json.dumps(addition.tags, ensure_ascii=True),
                addition.display_order,
                addition.source,
                now,
            )
            for addition in SOULMARK_DISPLAY_ADDITIONS
        ],
    )
    return SoulmarkDisplayBuildSummary(
        display_rows=len(display_rows),
        addition_rows=len(SOULMARK_DISPLAY_ADDITIONS),
    )


def _display_rows(
    rows_by_pet: dict[int, list[tuple[int, bool, bool, int | None]]],
    now: float,
) -> list[tuple[int, int, int, int, str, float]]:
    candidate_rows: list[tuple[int, int, int, str]] = []
    for pet_id, soulmarks in sorted(rows_by_pet.items()):
        parent_by_child = {
            int(child): soulmark_id
            for soulmark_id, _intensified, _is_adv, child in soulmarks
            if child is not None
        }
        for soulmark_id, intensified, is_adv, _child in sorted(soulmarks):
            root_id = soulmark_id
            seen: set[int] = set()
            while root_id in parent_by_child and root_id not in seen:
                seen.add(root_id)
                root_id = parent_by_child[root_id]
            display_kind = "advance" if is_adv else "intensified" if intensified else "base"
            candidate_rows.append((pet_id, soulmark_id, root_id, display_kind))

    kind_order = {"base": 0, "intensified": 1, "advance": 2}
    result: list[tuple[int, int, int, int, str, float]] = []
    for pet_id in sorted(rows_by_pet):
        pet_rows = sorted(
            (row for row in candidate_rows if row[0] == pet_id),
            key=lambda row: (row[2], kind_order[row[3]], row[1]),
        )
        result.extend(
            (pet_id, soulmark_id, root_id, index, display_kind, now)
            for index, (_pet_id, soulmark_id, root_id, display_kind) in enumerate(
                pet_rows
            )
        )
    return result


__all__ = [
    "SOULMARK_DISPLAY_ADDITIONS",
    "SoulmarkDisplayAddition",
    "SoulmarkDisplayBuildSummary",
    "replace_pet_soulmark_display_facts",
]
