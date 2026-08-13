# SPDX-License-Identifier: MIT
"""Source loading and normalization for published Autocard JSON assets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

JsonLoader = Callable[[str], tuple[dict[str, object], str]]


@dataclass(frozen=True, slots=True)
class AutocardData:
    cards: list[dict[str, object]]
    roles: list[dict[str, object]]
    natures: list[dict[str, object]]
    buffs: list[dict[str, object]]
    source: str


def load_autocard_data(
    load_json: JsonLoader,
    *,
    content_file: str,
    nature_file: str,
    role_file: str,
    buff_file: str,
) -> AutocardData:
    """Load the four official Autocard exports through one source boundary."""

    content_json, content_source = load_json(content_file)
    nature_json, nature_source = load_json(nature_file)
    role_json, role_source = load_json(role_file)
    buff_json, buff_source = load_json(buff_file)
    return AutocardData(
        cards=json_data_rows(content_json),
        roles=json_data_rows(role_json),
        natures=json_data_rows(nature_json),
        buffs=json_data_rows(buff_json),
        source="\n".join(
            sorted({buff_source, content_source, nature_source, role_source})
        ),
    )


def json_data_rows(raw: dict[str, object]) -> list[dict[str, object]]:
    """Return only object rows from the common Unity JSON ``data`` envelope."""

    rows = raw.get("data", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]
