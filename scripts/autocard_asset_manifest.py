# SPDX-License-Identifier: MIT
"""Derive optional群星牌 artwork requests from published data facts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import sqlite3

if __package__:
    from .json_value_helpers import as_int
else:
    from json_value_helpers import as_int

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AutocardAssetRequest:
    asset_kind: str
    asset_key: str
    path: str


def collect_autocard_asset_requests(
    conn: sqlite3.Connection,
) -> tuple[AutocardAssetRequest, ...] | None:
    try:
        card_rows = conn.execute(
            'SELECT id, raw_json FROM autocard_card ORDER BY id'
        ).fetchall()
    except sqlite3.OperationalError:
        card_rows = []
    try:
        role_rows = conn.execute(
            'SELECT role_id, pic_id FROM autocard_role_raw ORDER BY role_id'
        ).fetchall()
    except sqlite3.OperationalError:
        try:
            role_rows = conn.execute(
                'SELECT id, pic_id FROM autocard_role ORDER BY id'
            ).fetchall()
        except sqlite3.OperationalError:
            role_rows = []

    requests: dict[tuple[str, str], AutocardAssetRequest] = {}
    try:
        chip_rows = conn.execute('SELECT id FROM autocard_chip ORDER BY id').fetchall()
    except sqlite3.OperationalError:
        chip_rows = []
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name IN "
        "('autocard_card', 'autocard_role', 'autocard_role_raw', 'autocard_chip') LIMIT 1"
    ).fetchone():
        logger.warning('Autocard catalogue is unavailable for asset publication')
        return None
    for (chip_id,) in chip_rows:
        if _positive_int(chip_id) <= 0:
            continue
        key = f'autocardChip_{chip_id}'
        requests[('autocard_chip', key)] = AutocardAssetRequest(
            'autocard_chip',
            key,
            f'newseer/assets/game/ui/autocard/s2chip/{key}.png',
        )
    for item_id, raw_json in card_rows:
        try:
            item = json.loads(str(raw_json))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        pic_id = _positive_int(item.get('picID', item.get('pic_id', 0)))
        card_id = _positive_int(item_id)
        image_id = pic_id if card_id < 20000 and pic_id > 0 else card_id
        if image_id <= 0:
            continue
        key = f'card_{image_id}'
        requests[('autocard_card', key)] = AutocardAssetRequest(
            'autocard_card',
            key,
            f'newseer/assets/art/autocard/texture/cards/{key}.png',
        )
    for _role_id, pic_id_value in role_rows:
        pic_id = _positive_int(pic_id_value)
        if pic_id <= 0:
            continue
        key = f'role_{pic_id}'
        requests[('autocard_role', key)] = AutocardAssetRequest(
            'autocard_role',
            key,
            f'newseer/assets/art/autocard/texture/roles/card/{key}.png',
        )
    return tuple(requests.values())


def _positive_int(value: object) -> int:
    return max(0, as_int(value))
