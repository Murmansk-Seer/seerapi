# SPDX-License-Identifier: MIT
"""Pure parsers for the official item-exchange shop source files."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True, slots=True)
class ItemExchangePrice:
    source_key: str
    source_name: str
    source_entry_id: int
    item_id: int
    item_name: str
    item_quantity: int
    currency_item_id: int
    amount: int
    purchase_limit: int | None
    start_time: int
    end_time: int
    currency_name: str = ""


def parse_commodity_shop(
    data: bytes,
    *,
    source_key: str,
    source_name: str,
) -> list[ItemExchangePrice]:
    """Parse standard Unity commodity-shop rows into exchange-price facts."""

    raw = json.loads(data.decode("utf-8-sig"))
    rows = raw.get("item", [])
    if not isinstance(rows, list):
        return []

    result: list[ItemExchangePrice] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        commodity = str(row.get("commodity", ""))
        parts = commodity.split("_")
        if len(parts) != 3 or parts[0] != "1":
            continue
        try:
            item_id = int(parts[1])
            commodity_quantity = int(parts[2])
        except ValueError:
            continue

        source_entry_id = _item_int(row, "id")
        currency_item_id = _item_int(row, "consumeitemid")
        amount = _item_int(row, "price")
        item_quantity = _item_int(row, "quantity") or commodity_quantity
        if (
            source_entry_id <= 0
            or item_id <= 0
            or item_quantity <= 0
            or currency_item_id <= 0
            or amount <= 0
        ):
            continue
        limit = _item_int(row, "limit")
        result.append(
            ItemExchangePrice(
                source_key=source_key,
                source_name=source_name,
                source_entry_id=source_entry_id,
                item_id=item_id,
                item_name=_item_text(row, "item_name", "itemname").strip(),
                item_quantity=item_quantity,
                currency_item_id=currency_item_id,
                amount=amount,
                purchase_limit=limit if limit > 0 else None,
                start_time=_item_int(row, "timestart", "starttime"),
                end_time=_item_int(row, "timeend", "endtime"),
            )
        )
    return result


def parse_special_skill_shop(
    data: bytes,
    *,
    source_key: str,
    source_name: str,
) -> list[ItemExchangePrice]:
    """Parse the special-skill shop's distinct item/coin field layout."""

    raw = json.loads(data.decode("utf-8-sig"))
    rows = raw.get("item", [])
    if not isinstance(rows, list):
        return []

    result: list[ItemExchangePrice] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_entry_id = _item_int(row, "id")
        item_id = _item_int(row, "item_id")
        currency_item_id = _item_int(row, "coin_id")
        amount = _item_int(row, "price")
        if (
            source_entry_id <= 0
            or item_id <= 0
            or currency_item_id <= 0
            or amount <= 0
        ):
            continue
        limit = _item_int(row, "limit")
        result.append(
            ItemExchangePrice(
                source_key=source_key,
                source_name=source_name,
                source_entry_id=source_entry_id,
                item_id=item_id,
                item_name=_item_text(row, "item_name", "itemname").strip(),
                item_quantity=1,
                currency_item_id=currency_item_id,
                amount=amount,
                purchase_limit=limit if limit > 0 else None,
                start_time=0,
                end_time=0,
            )
        )
    return result


def _item_int(item: dict[object, object], *names: str) -> int:
    for name in names:
        if name not in item:
            continue
        try:
            return int(item.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _item_text(item: dict[object, object], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ""
