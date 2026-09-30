# SPDX-License-Identifier: MIT
"""Pure parsers for official effect-description and status metadata."""

from __future__ import annotations

from dataclasses import dataclass
import json

if __package__:
    from .json_value_helpers import item_int
else:
    from json_value_helpers import item_int


@dataclass(frozen=True, slots=True)
class EffectDescription:
    effect_id: int
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class SpecialEffectStatus:
    status_id: int
    name: str
    description: str
    show_monster_id: int
    variants: tuple[SpecialEffectStatusVariant, ...] = ()


@dataclass(frozen=True, slots=True)
class SpecialEffectStatusVariant:
    status_id: int
    value: int
    name: str
    description: str
    icon_key: str


def parse_effect_descriptions(data: bytes) -> list[EffectDescription]:
    """Read named exclusive-effect descriptions from ``effectDes.json``."""

    raw = json.loads(data.decode('utf-8-sig'))
    root = raw.get('root')
    if not isinstance(root, dict):
        return []
    rows = root.get('item', [])
    if not isinstance(rows, list):
        return []

    result: list[EffectDescription] = []
    seen_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict) or _item_int(row, 'kind') != 1:
            continue
        effect_id = _item_int(row, 'id')
        name = _item_text(row, 'kinddes').strip()
        description = _item_text(row, 'desc').strip()
        if effect_id <= 0 or not name or not description or effect_id in seen_ids:
            continue
        seen_ids.add(effect_id)
        result.append(EffectDescription(effect_id, name, description))
    return result


def parse_special_effect_statuses(data: bytes) -> list[SpecialEffectStatus]:
    """Read displayable status-name variants from ``signIconFight.json``."""

    raw = json.loads(data.decode('utf-8-sig'))
    config = raw.get('config')
    if not isinstance(config, dict):
        return []
    rows = config.get('item', [])
    if not isinstance(rows, list):
        return []

    result: list[SpecialEffectStatus] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        status_id = _item_int(row, 'id')
        if status_id <= 0:
            continue
        names = tuple(
            dict.fromkeys(
                name
                for name in (
                    _item_text(row, 'dec').strip(),
                    _item_text(row, 'tips').strip(),
                )
                if name
            )
        )
        description = _item_text(row, 'des').strip()
        show_monster_id = _item_int(row, 'show_monster')
        indexed_descriptions = _indexed_values(row.get('sp_des'))
        indexed_icons = _indexed_values(row.get('sp_icon'))
        variants = tuple(
            SpecialEffectStatusVariant(
                status_id=status_id,
                value=value,
                name=name,
                description=indexed_descriptions.get(value, ''),
                icon_key=f'{status_id}_{_icon_suffix(indexed_icons.get(value), value)}',
            )
            for value, name in sorted(_indexed_values(row.get('sp_tips')).items())
        )
        for name in names:
            key = (status_id, name)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                SpecialEffectStatus(
                    status_id,
                    name,
                    description,
                    show_monster_id,
                    variants,
                )
            )
    return sorted(result, key=lambda item: (item.status_id, item.name))


def _indexed_values(value: object) -> dict[int, str]:
    if not isinstance(value, list):
        return {}
    result: dict[int, str] = {}
    for entry in value:
        if not isinstance(entry, str) or '_' not in entry:
            continue
        raw_index, text = entry.split('_', 1)
        if raw_index.isdecimal() and text.strip():
            result[int(raw_index)] = text.strip()
    return result


def _icon_suffix(explicit: str | None, value: int) -> str:
    return explicit if explicit is not None and explicit.isdecimal() else str(value)


def _item_int(item: dict[object, object], *names: str) -> int:
    return item_int({str(key): value for key, value in item.items()}, *names)


def _item_text(item: dict[object, object], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ''
