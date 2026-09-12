"""Publish build-time-resolved pet special-effect and soulmark-display facts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import sqlite3

from .pet_soulmark_display_facts import replace_pet_soulmark_display_facts
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
    soulmark_display_addition_rows: int


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
    contexts: dict[tuple[int, str, str, int, str], set[str]] = defaultdict(set)
    for issue in issues:
        key = (
            issue.pet_id,
            issue.effect_name,
            issue.candidate_kind,
            issue.candidate_id,
            issue.reason,
        )
        values = contexts[key]
        if issue.context:
            values.add(issue.context)
    issue_rows = [
        (*key, "\n\n".join(sorted(values)) or None, now)
        for key, values in sorted(contexts.items())
    ]
    connection.executemany(
        """
        INSERT INTO pet_special_effect_issue
            (pet_id, effect_name, candidate_kind, candidate_id, reason, context, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        issue_rows,
    )
    return len(ordered_facts), len(source_rows), len(issue_rows)


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
    soulmark_display = replace_pet_soulmark_display_facts(connection, now=now)
    return PetSpecialEffectBuildSummary(
        facts=fact_count,
        sources=source_count,
        issues=issue_count,
        soulmark_display_rows=soulmark_display.display_rows,
        soulmark_display_addition_rows=soulmark_display.addition_rows,
    )


__all__ = ["PetSpecialEffectBuildSummary", "replace_pet_special_effect_facts"]
