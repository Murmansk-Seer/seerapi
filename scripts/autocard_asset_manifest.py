# SPDX-License-Identifier: MIT
"""Derive optional群星牌 artwork requests from published data facts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import sqlite3

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
        role_rows = conn.execute(
            'SELECT id, pic_id FROM autocard_role ORDER BY id'
        ).fetchall()
    except sqlite3.OperationalError:
        logger.warning('Autocard catalogue is unavailable for asset publication')
        return None

    requests: dict[tuple[str, str], AutocardAssetRequest] = {}
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
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
