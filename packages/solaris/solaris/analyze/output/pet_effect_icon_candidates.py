"""Find artwork candidates without assigning a battle status to a pet."""

from __future__ import annotations

from collections import defaultdict
import json
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pet_special_effect_types import SpecialEffectFact


def _exact_text(value: str) -> str:
    return value.replace('\\n', '\n').replace('\r\n', '\n').strip()


def candidate_icon_rows(
    connection: sqlite3.Connection, facts: list[SpecialEffectFact]
) -> list[tuple[int, str, int, str | None]]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name='special_effect_status_config'"
    ).fetchone():
        return []
    by_name: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    by_id: dict[int, dict] = {}
    for status_id, raw in connection.execute(
        'SELECT status_id,config_json FROM special_effect_status_config ORDER BY status_id'
    ):
        config = json.loads(raw)
        name = config.get('dec')
        if isinstance(name, str):
            by_name[name.strip()].append((status_id, config))
            by_id[status_id] = config
    available = (
        {
            str(key)
            for (key,) in connection.execute(
                "SELECT asset_key FROM render_asset_manifest WHERE asset_kind='sign_buff' AND available=1"
            )
        }
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE name='render_asset_manifest'"
        ).fetchone()
        else set()
    )
    bound = {
        (fact.pet_id, fact.status_id) for fact in facts if fact.status_id is not None
    }
    rows = []
    for fact in facts:
        if not fact.display_in_pet_info:
            continue
        if fact.status_id is None:
            if fact.icons or not _has_local_evidence(fact):
                continue
            name, text = fact.name, fact.description
        else:
            reference = by_id.get(fact.status_id, {})
            name, text = reference.get('dec'), reference.get('des')
        if not isinstance(name, str) or not isinstance(text, str):
            continue
        description = _exact_text(text)
        if not description:
            continue
        for status_id, config in by_name.get(name.strip(), ()):
            candidate_text = config.get('des')
            if (
                not isinstance(candidate_text, str)
                or _exact_text(candidate_text) != description
                or any(
                    config.get(key) for key in ('frame', 'sp_icon', 'sp_tips', 'sp_des')
                )
            ):
                continue
            key = str(status_id)
            restrictions = config.get('show_monster', [])
            if fact.status_id is not None:
                if (
                    (fact.pet_id, status_id) in bound
                    or key not in available
                    or not _display_rules_allow_pet(restrictions, fact.pet_id)
                ):
                    continue
            elif restrictions:
                continue
            rows.append(
                (
                    fact.pet_id,
                    fact.effect_key,
                    status_id,
                    key if key in available else None,
                )
            )
    return rows


def _display_rules_allow_pet(rules: object, pet_id: int) -> bool:
    if not isinstance(rules, list):
        return False
    for raw in rules:
        parts = raw.split('_') if isinstance(raw, str) else ()
        if len(parts) != 4 or any(not part.isdecimal() for part in parts):
            return False
        _, target, icon, frame = map(int, parts)
        if target != pet_id or not (icon or frame):
            return False
    return True


def _has_local_evidence(fact: SpecialEffectFact) -> bool:
    return any(
        source.kind == 'pet_glossary' and source.rule == 'direct_pet_glossary'
        for source in fact.sources
    ) and any(
        (source.kind, source.rule)
        in {
            ('skill', 'skill_highlight_exact'),
            ('soulmark', 'soulmark_highlight_exact'),
        }
        for source in fact.sources
    )
