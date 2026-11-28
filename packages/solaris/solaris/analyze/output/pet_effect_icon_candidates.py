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
    for status_id, raw in connection.execute(
        'SELECT status_id,config_json FROM special_effect_status_config ORDER BY status_id'
    ):
        config = json.loads(raw)
        name = config.get('dec')
        if isinstance(name, str):
            by_name[name.strip()].append((status_id, config))
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
    rows = []
    for fact in facts:
        if (
            fact.status_id is not None
            or fact.icons
            or not fact.display_in_pet_info
            or not fact.description
            or not _has_local_evidence(fact)
        ):
            continue
        description = _exact_text(fact.description)
        for status_id, config in by_name.get(fact.name, ()):
            text = config.get('des')
            if (
                not isinstance(text, str)
                or _exact_text(text) != description
                or any(
                    config.get(key)
                    for key in ('show_monster', 'frame', 'sp_icon', 'sp_tips', 'sp_des')
                )
            ):
                continue
            key = str(status_id)
            rows.append(
                (
                    fact.pet_id,
                    fact.effect_key,
                    status_id,
                    key if key in available else None,
                )
            )
    return rows


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
