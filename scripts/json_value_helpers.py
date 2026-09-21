# SPDX-License-Identifier: MIT
"""Small pure helpers for official JSON-object values."""

from __future__ import annotations

import json


def as_int(value: object, *, default: int = 0) -> int:
    """Convert JSON scalar values to integers without accepting containers."""
    if not isinstance(value, (str, bytes, bytearray, int, float)):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def item_int(item: dict[str, object], *names: str) -> int:
    """Return the first present field as an integer, defaulting to zero."""
    for name in names:
        if name not in item:
            continue
        return as_int(item.get(name, 0) or 0)
    return 0


def item_text(item: dict[str, object], *names: str) -> str:
    """Return the first non-null field as text, defaulting to an empty string."""
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ''


def compact_json(item: dict[str, object]) -> str:
    """Serialize official JSON without changing Chinese text or adding whitespace."""
    return json.dumps(item, ensure_ascii=False, separators=(',', ':'))
