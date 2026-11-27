"""Structured client panel references; not skill or status ownership inference."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
import re
import sqlite3

from .pet_special_effect_types import (
    EffectResolutionIssue,
    EffectSource,
    SpecialEffectFactAccumulator,
    StatusCandidate,
)

TAGS = re.compile(r'<[^>]*>')
ANNOTATION = re.compile(
    r'^(?:下场保留|上限\s*\d+\s*层)(?:[，,、]\s*(?:下场保留|上限\s*\d+\s*层))*$'
)


@dataclass(frozen=True, slots=True)
class PetEffectPanel:
    id: int
    pet_id: int
    effecticonid: int
    description: str
    is_adv: bool
    config_version: str


def panel_headings(description: str) -> tuple[tuple[str, str], ...]:
    headings = []
    for line in description.splitlines():
        if not re.match(r'^\s*<indent=0>\s*<sprite=5>\s*<indent=15>', line):
            continue
        raw = unescape(TAGS.sub('', line)).strip()
        if not raw.endswith(('：', ':')):
            continue
        name = raw[:-1].strip()
        annotated = re.fullmatch(r'(.*?)[（(]([^（）()]*)[）)]', name)
        if annotated and ANNOTATION.fullmatch(annotated[2]):
            name = annotated[1].strip()
        if name:
            headings.append((name, raw))
    return tuple(dict.fromkeys(headings))


def replace_panel_table(
    connection: sqlite3.Connection, panels: tuple[PetEffectPanel, ...]
) -> None:
    connection.execute('DROP TABLE IF EXISTS pet_effect_panel')
    connection.execute(
        'CREATE TABLE pet_effect_panel (id INTEGER PRIMARY KEY, pet_id INTEGER NOT NULL, effecticonid INTEGER NOT NULL, description TEXT NOT NULL, is_adv INTEGER NOT NULL, config_version TEXT NOT NULL)'
    )
    connection.executemany(
        'INSERT INTO pet_effect_panel VALUES (?,?,?,?,?,?)',
        [
            (p.id, p.pet_id, p.effecticonid, p.description, p.is_adv, p.config_version)
            for p in panels
        ],
    )


def add_panel_references(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    statuses: dict[str, list[StatusCandidate]],
    issues: list[EffectResolutionIssue],
) -> None:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='pet_effect_panel'"
    ).fetchone():
        return
    for panel_id, pet_id, effecticonid, description, _, version in connection.execute(
        'SELECT * FROM pet_effect_panel ORDER BY id'
    ):
        if not connection.execute('SELECT 1 FROM pet WHERE id=?', (pet_id,)).fetchone():
            continue
        for heading, raw_heading in panel_headings(description):
            candidates = {s.id: s for s in statuses.get(heading, ())}
            detail = json.dumps(
                {
                    'heading': heading,
                    'raw_heading': raw_heading,
                    'config_version': version,
                    'effecticonid': effecticonid,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            if len(candidates) != 1:
                for candidate_id in candidates or {0: None}:
                    issues.append(
                        EffectResolutionIssue(
                            pet_id,
                            heading,
                            'status',
                            candidate_id,
                            'ambiguous_panel_heading'
                            if candidates
                            else 'unmatched_panel_heading',
                            detail,
                        )
                    )
                continue
            status = next(iter(candidates.values()))
            # A pre-existing differently named term in the same panel is evidence
            # of a conflict, not permission to invent an alias or a duplicate card.
            existing = [f for f in facts.facts if f.pet_id == pet_id]
            matching = [f for f in existing if f.name == heading]
            other_headings = {h for h, _ in panel_headings(description)}
            unresolved = [
                f
                for f in existing
                if f.glossary_id is not None
                and f.status_id is None
                and f.name not in other_headings
                and any(
                    source.kind == 'soulmark' and source.id == effecticonid
                    for source in f.sources
                )
            ]
            # This can only veto a new heading pending reconciliation. Text
            # presence never supplies an ID, icon, alias or positive relation.
            body = TAGS.sub('', description)
            conflicts = [f for f in unresolved if f.name not in body]
            if conflicts and not matching:
                issues.append(
                    EffectResolutionIssue(
                        pet_id,
                        heading,
                        'status',
                        status.id,
                        'panel_conflicting_existing_term',
                        detail,
                    )
                )
                continue
            if any(f.status_id not in (None, status.id) for f in matching):
                issues.append(
                    EffectResolutionIssue(
                        pet_id,
                        heading,
                        'status',
                        status.id,
                        'panel_conflicting_existing_status',
                        detail,
                    )
                )
                continue
            if len(matching) > 1:
                issues.append(
                    EffectResolutionIssue(
                        pet_id,
                        heading,
                        'status',
                        status.id,
                        'ambiguous_panel_existing_fact',
                        detail,
                    )
                )
                continue
            facts.add(
                pet_id=pet_id,
                name=heading,
                description=status.description or None,
                status_id=status.id,
                glossary_id=matching[0].glossary_id if matching else None,
                source=EffectSource(
                    'pet_effect_panel', panel_id, 'panel_heading_unique_status', detail
                ),
            )


__all__ = [
    'PetEffectPanel',
    'add_panel_references',
    'panel_headings',
    'replace_panel_table',
]
