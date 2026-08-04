"""Publish build-time-resolved pet special-effect and soulmark-display facts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import sqlite3

from .pet_special_effect_resolution import collect_pet_special_effect_facts
from .pet_special_effect_types import (
    EffectResolutionIssue,
    SpecialEffectFactAccumulator,
)


@dataclass(frozen=True, slots=True)
class PetSpecialEffectBuildSummary:
    """The number of deterministic facts emitted for a published data release."""

    facts: int
    sources: int
    issues: int
    soulmark_display_rows: int


def _replace_special_effect_tables(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    issues: list[EffectResolutionIssue],
    now: float,
) -> tuple[int, int, int]:
    connection.executescript(
        """
        DROP TABLE IF EXISTS pet_special_effect_source;
        DROP TABLE IF EXISTS pet_special_effect_issue;
        DROP TABLE IF EXISTS pet_special_effect;
        CREATE TABLE pet_special_effect (
            pet_id INTEGER NOT NULL,
            effect_key TEXT NOT NULL,
            glossary_id INTEGER,
            status_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            sort_id INTEGER,
            sort_kind TEXT NOT NULL,
            primary_rule TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (pet_id, effect_key)
        );
        CREATE UNIQUE INDEX idx_pet_special_effect_glossary
        ON pet_special_effect (pet_id, glossary_id)
        WHERE glossary_id IS NOT NULL;
        CREATE UNIQUE INDEX idx_pet_special_effect_status
        ON pet_special_effect (pet_id, status_id)
        WHERE status_id IS NOT NULL;
        CREATE TABLE pet_special_effect_source (
            pet_id INTEGER NOT NULL,
            effect_key TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            resolution_rule TEXT NOT NULL,
            source_detail TEXT,
            updated_at REAL NOT NULL,
            PRIMARY KEY (
                pet_id, effect_key, source_kind, source_id, resolution_rule
            )
        );
        CREATE TABLE pet_special_effect_issue (
            pet_id INTEGER NOT NULL,
            effect_name TEXT NOT NULL,
            candidate_kind TEXT NOT NULL,
            candidate_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            context TEXT,
            updated_at REAL NOT NULL,
            PRIMARY KEY (pet_id, effect_name, candidate_kind, candidate_id, reason)
        );
        """
    )
    ordered_facts = sorted(
        facts.facts,
        key=lambda fact: (
            fact.pet_id,
            fact.sort_id is None,
            fact.sort_id or 0,
            fact.discovery_index,
        ),
    )
    connection.executemany(
        """
        INSERT INTO pet_special_effect
            (
                pet_id, effect_key, glossary_id, status_id, name, description,
                sort_id, sort_kind, primary_rule, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                fact.pet_id,
                fact.effect_key,
                fact.glossary_id,
                fact.status_id,
                fact.name,
                fact.description,
                fact.sort_id,
                fact.sort_kind,
                fact.primary_rule,
                now,
            )
            for fact in ordered_facts
        ],
    )
    source_rows = [
        (
            fact.pet_id,
            fact.effect_key,
            source.kind,
            source.id,
            source.rule,
            source.detail,
            now,
        )
        for fact in ordered_facts
        for source in sorted(
            fact.sources,
            key=lambda source: (
                source.kind,
                source.id,
                source.rule,
                source.detail or "",
            ),
        )
    ]
    connection.executemany(
        """
        INSERT INTO pet_special_effect_source
            (
                pet_id, effect_key, source_kind, source_id, resolution_rule,
                source_detail, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        source_rows,
    )
    issue_rows = sorted(
        {
            (
                issue.pet_id,
                issue.effect_name,
                issue.candidate_kind,
                issue.candidate_id,
                issue.reason,
                issue.context,
                now,
            )
            for issue in issues
        }
    )
    connection.executemany(
        """
        INSERT INTO pet_special_effect_issue
            (pet_id, effect_name, candidate_kind, candidate_id, reason, context, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        issue_rows,
    )
    return len(ordered_facts), len(source_rows), len(issue_rows)


def _replace_soulmark_display_table(
    connection: sqlite3.Connection,
    now: float,
) -> int:
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
    display_rows: list[tuple[int, int, int, int, str, float]] = []
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
            display_rows.append(
                (pet_id, soulmark_id, root_id, 0, display_kind, now)
            )
    ordered_rows: list[tuple[int, int, int, int, str, float]] = []
    kind_order = {"base": 0, "intensified": 1, "advance": 2}
    for pet_id in sorted(rows_by_pet):
        pet_rows = sorted(
            (row for row in display_rows if row[0] == pet_id),
            key=lambda row: (row[2], kind_order[row[4]], row[1]),
        )
        ordered_rows.extend(
            (
                pet_id,
                soulmark_id,
                root_soulmark_id,
                index,
                display_kind,
                updated_at,
            )
            for index, (
                _pet_id,
                soulmark_id,
                root_soulmark_id,
                _display_order,
                display_kind,
                updated_at,
            ) in enumerate(pet_rows)
        )
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
        """
    )
    connection.executemany(
        """
        INSERT INTO pet_soulmark_display
            (pet_id, soulmark_id, root_soulmark_id, display_order, display_kind, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ordered_rows,
    )
    return len(ordered_rows)


def replace_pet_special_effect_facts(
    connection: sqlite3.Connection,
    *,
    now: float,
) -> PetSpecialEffectBuildSummary:
    """Replace published special-effect and soulmark-display facts in one DB."""
    facts, issues = collect_pet_special_effect_facts(connection)
    fact_count, source_count, issue_count = _replace_special_effect_tables(
        connection,
        facts,
        issues,
        now,
    )
    soulmark_display_rows = _replace_soulmark_display_table(connection, now)
    return PetSpecialEffectBuildSummary(
        facts=fact_count,
        sources=source_count,
        issues=issue_count,
        soulmark_display_rows=soulmark_display_rows,
    )


__all__ = ["PetSpecialEffectBuildSummary", "replace_pet_special_effect_facts"]
