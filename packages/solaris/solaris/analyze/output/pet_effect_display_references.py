"""Conditional client display references, explicitly not static ownership."""

from __future__ import annotations

from collections import defaultdict
import json
import sqlite3

from .pet_special_effect_types import (
    EffectResolutionIssue,
    EffectSource,
    SpecialEffectFactAccumulator,
)


def add_display_references(
    connection: sqlite3.Connection,
    facts: SpecialEffectFactAccumulator,
    issues: list[EffectResolutionIssue],
) -> None:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='special_effect_status_config'"
    ).fetchone():
        return
    for status_id, raw, version in connection.execute(
        'SELECT status_id,config_json,config_version FROM special_effect_status_config ORDER BY status_id'
    ):
        config = json.loads(raw)
        name = str(config.get('dec') or config.get('tips') or '').strip()
        if not name:
            continue
        by_pet = defaultdict(list)
        for rule in config.get('show_monster', []):
            parts = rule.split('_')
            if len(parts) != 4 or not all(value.isdecimal() for value in parts):
                continue
            _, pet_id, show_icon, show_frame = map(int, parts)
            if (
                show_icon not in (0, 1)
                or show_frame not in (0, 1)
                or not (show_icon or show_frame)
            ):
                continue
            by_pet[pet_id].append(rule)
        for pet_id, rules in by_pet.items():
            if not connection.execute(
                'SELECT 1 FROM pet WHERE id=?', (pet_id,)
            ).fetchone():
                continue
            matches = [
                f
                for f in facts.facts
                if f.pet_id == pet_id and (f.status_id == status_id or f.name == name)
            ]
            detail = json.dumps(
                {'config_version': version, 'show_monster': rules},
                ensure_ascii=False,
                sort_keys=True,
            )
            if len(matches) > 1 or any(
                f.status_id not in (None, status_id) for f in matches
            ):
                issues.append(
                    EffectResolutionIssue(
                        pet_id,
                        name,
                        'status',
                        status_id,
                        'ambiguous_client_display_reference',
                        detail,
                    )
                )
                continue
            facts.add(
                pet_id=pet_id,
                name=name,
                description=str(config.get('des') or '').replace('\\n', '\n') or None,
                status_id=status_id,
                glossary_id=matches[0].glossary_id if matches else None,
                source=EffectSource(
                    'client_status_display',
                    status_id,
                    'client_conditional_display',
                    detail,
                ),
            )


__all__ = ['add_display_references']
