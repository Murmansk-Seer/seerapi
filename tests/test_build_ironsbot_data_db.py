import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_ironsbot_data_db.py"
SPEC = importlib.util.spec_from_file_location("build_ironsbot_data_db", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def test_parse_battlepass_shop_keeps_exchange_price_details() -> None:
    payload = {
        "item": [
            {
                "commodity": "1_1728296_1",
                "consumeitemid": 1726710,
                "id": 1005,
                "limit": 6,
                "price": 2000,
                "quantity": 1,
                "timestart": 100,
                "timeend": 200,
            },
            {
                "commodity": "2_1728296_1",
                "consumeitemid": 1726710,
                "id": 1006,
                "limit": 6,
                "price": 2000,
                "quantity": 1,
            },
        ]
    }

    prices = builder._parse_battlepass_shop(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    assert prices == [
        builder.ItemExchangePrice(
            source_key="battlepass_shop",
            source_name="战令商店",
            source_entry_id=1005,
            item_id=1728296,
            item_quantity=1,
            currency_item_id=1726710,
            amount=2000,
            purchase_limit=6,
            start_time=100,
            end_time=200,
        )
    ]


def test_parse_special_skill_shop_reads_resonance_crystal_price() -> None:
    payload = {
        "item": [
            {
                "coin_id": 1726992,
                "id": 1,
                "item_id": 1725170,
                "limit": 1,
                "price": 200,
            }
        ]
    }

    prices = builder._parse_special_skill_shop(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    assert prices == [
        builder.ItemExchangePrice(
            source_key="special_skill_shop",
            source_name="追加技能商店",
            source_entry_id=1,
            item_id=1725170,
            item_quantity=1,
            currency_item_id=1726992,
            amount=200,
            purchase_limit=1,
            start_time=0,
            end_time=0,
        )
    ]


def test_merge_writes_item_exchange_prices(tmp_path) -> None:
    database = tmp_path / "ironsbot-data.sqlite"
    price = builder.ItemExchangePrice(
        source_key="battlepass_shop",
        source_name="战令商店",
        source_entry_id=1005,
        item_id=1728296,
        item_quantity=1,
        currency_item_id=1726710,
        amount=2000,
        purchase_limit=6,
        start_time=0,
        end_time=0,
    )
    config_data = builder.ConfigPackageData(
        version="test",
        bundle_url="https://example.invalid/config.bytes",
        mintmark_quality={},
        skin_store_prices=[],
        skin_shop_prices=[],
        skin_item_tips={},
        soulmark_icons=[],
    )
    autocard_data = builder.AutocardData(
        cards=[],
        roles=[],
        natures=[],
        source="test",
    )

    builder._merge_ironsbot_tables(
        database,
        config_data=config_data,
        autocard_data=autocard_data,
        item_exchange_prices=[price],
        weekly_preview_probe={},
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT item_id, currency_item_id, amount, purchase_limit, source_name
            FROM item_exchange_price
            """
        ).fetchone()
    assert row == (1728296, 1726710, 2000, 6, "战令商店")
