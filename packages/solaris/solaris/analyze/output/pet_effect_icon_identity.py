"""Assign icons only through official IDs, never through effect descriptions."""

from __future__ import annotations

import json
import sqlite3

from .pet_special_effect_types import (
    EffectResolutionIssue,
    EffectSource,
    SpecialEffectFact,
    SpecialEffectFactAccumulator,
)


def _branch_reference_applies(
    connection: sqlite3.Connection, state: SpecialEffectFact, pet_id: int, value: int
) -> bool:
    if not any(source.kind == 'client_status_display' for source in state.sources):
        return True
    if any(source.kind == 'pet_effect_panel' for source in state.sources):
        return True
    row = connection.execute(
        'SELECT config_json FROM special_effect_status_config WHERE status_id=?',
        (state.status_id,),
    ).fetchone()
    if row is None:
        return False
    thresholds = {}
    for raw in json.loads(row[0]).get('show_monster', []):
        parts = raw.split('_')
        if len(parts) == 4 and all(part.isdecimal() for part in parts):
            key, target, icon, frame = map(int, parts)
            thresholds.setdefault(key, (target, icon, frame))
    applicable = [key for key in thresholds if key <= value]
    if not applicable:
        return False
    target, icon, frame = thresholds[max(applicable)]
    return target == pet_id and bool(icon or frame)


def assign_icon_identities(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    issues: list[EffectResolutionIssue],
) -> None:
    has_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='special_effect_glossary_icon'"
    ).fetchone()
    icons = (
        dict(
            connection.execute(
                'SELECT glossary_id,icon_id FROM special_effect_glossary_icon'
            )
        )
        if has_table
        else {}
    )
    for fact in facts.facts:
        icon = icons.get(fact.glossary_id, 0)
        if icon > 0:
            fact.icon_kind, fact.icon_key = 'abnormal', str(icon)
        elif fact.status_id is not None:
            fact.icon_kind, fact.icon_key = 'sign_buff', str(fact.status_id)
    has_variants = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='special_effect_status_variant'"
    ).fetchone()
    if not has_variants:
        return
    for fact in facts.facts:
        if fact.icon_kind is not None:
            continue
        same_name = [
            f for f in facts.facts if f.pet_id == fact.pet_id and f.name == fact.name
        ]
        if len(same_name) != 1:
            continue
        confirmed = {
            f.status_id: f
            for f in facts.facts
            if f.pet_id == fact.pet_id and f.status_id is not None
        }
        candidates = [
            (sid, value, key)
            for sid, value, key in connection.execute(
                'SELECT status_id,variant_value,icon_key FROM special_effect_status_variant WHERE name=?',
                (fact.name,),
            )
            if sid in confirmed
            and _branch_reference_applies(
                connection, confirmed[sid], fact.pet_id, value
            )
        ]
        if len(candidates) == 1:
            status_id, value, key = candidates[0]
            fact.icon_kind, fact.icon_key = 'sign_buff', key
            fact.sources.add(
                EffectSource(
                    'client_status_variant',
                    status_id,
                    'client_variant_display_reference',
                    json.dumps({'state_value': value, 'icon_key': key}, sort_keys=True),
                )
            )
        elif candidates:
            for status_id, value, key in candidates:
                issues.append(
                    EffectResolutionIssue(
                        fact.pet_id,
                        fact.name,
                        'status_variant',
                        status_id,
                        'ambiguous_client_variant_reference',
                        json.dumps(
                            {'state_value': value, 'icon_key': key}, sort_keys=True
                        ),
                    )
                )


__all__ = ['assign_icon_identities']
