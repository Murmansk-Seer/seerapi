"""Separate state containers from independently useful pet effect cards."""

from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3

from .pet_effect_icon_identity import _branch_reference_applies
from .pet_special_effect_types import (
    EffectResolutionIssue,
    SpecialEffectFactAccumulator,
)


@dataclass(frozen=True, slots=True)
class EffectDisplayDecision:
    pet_id: int
    effect_key: str
    name: str
    status_id: int
    display_in_pet_info: bool
    reason: str
    branch_values: tuple[int, ...] = ()


def status_container_decisions(
    connection: sqlite3.Connection, facts: SpecialEffectFactAccumulator
) -> list[EffectDisplayDecision]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='special_effect_status_variant'"
    ).fetchone():
        return []
    decisions = []
    for parent in facts.facts:
        if parent.status_id is None:
            continue
        variants = list(
            connection.execute(
                'SELECT variant_value,name FROM special_effect_status_variant WHERE status_id=? ORDER BY variant_value',
                (parent.status_id,),
            )
        )
        if not variants:
            continue
        reason = 'complete_named_branches'
        values: list[int] = []
        if parent.description and parent.description.strip():
            reason = 'independent_description'
        elif parent.glossary_id is not None:
            reason = 'independent_glossary'
        elif not parent.sources or any(
            s.kind != 'client_status_display' for s in parent.sources
        ):
            reason = 'independent_source'
        else:
            for value, name in variants:
                if not _branch_reference_applies(
                    connection, parent, parent.pet_id, value
                ):
                    continue
                values.append(value)
                matches = [
                    child
                    for child in facts.facts
                    if child.pet_id == parent.pet_id and child.name == name
                ]
                if len(matches) != 1 or matches[0] is parent:
                    reason = 'incomplete_or_ambiguous_branches'
                    continue
                if not any(
                    s.kind == 'client_status_variant'
                    and s.id == parent.status_id
                    and s.detail is not None
                    and json.loads(s.detail).get('state_value') == value
                    for s in matches[0].sources
                ):
                    reason = 'incomplete_or_ambiguous_branches'
            if not values:
                reason = 'no_applicable_branches'
        decisions.append(
            EffectDisplayDecision(
                parent.pet_id,
                parent.effect_key,
                parent.name,
                parent.status_id,
                reason != 'complete_named_branches',
                reason,
                tuple(values),
            )
        )
    return decisions


def assign_pet_info_visibility(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    issues: list[EffectResolutionIssue],
) -> None:
    by_key = {(f.pet_id, f.effect_key): f for f in facts.facts}
    for decision in status_container_decisions(connection, facts):
        by_key[
            decision.pet_id, decision.effect_key
        ].display_in_pet_info = decision.display_in_pet_info
        if decision.reason in {
            'incomplete_or_ambiguous_branches',
            'no_applicable_branches',
        }:
            issues.append(
                EffectResolutionIssue(
                    decision.pet_id,
                    decision.name,
                    'status',
                    decision.status_id,
                    'unresolved_status_container_display',
                    decision.reason,
                )
            )
