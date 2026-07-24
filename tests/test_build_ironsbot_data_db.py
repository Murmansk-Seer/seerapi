import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys

from PIL import Image
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_ironsbot_data_db.py"
)
SPEC = importlib.util.spec_from_file_location("build_ironsbot_data_db", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


@pytest.fixture(autouse=True)
def _isolate_effect_icon_png_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        builder,
        "EFFECT_ICON_PNG_CACHE_DIR",
        tmp_path / "effect-icon-png",
    )


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
            item_name="",
            item_quantity=1,
            currency_item_id=1726710,
            amount=2000,
            purchase_limit=6,
            start_time=100,
            end_time=200,
        )
    ]


def test_parse_special_skill_shop_reads_current_skill_scroll_prices() -> None:
    payload = {
        "item": [
            {
                "coin_id": 1726992,
                "id": 3,
                "item_id": 1727009,
                "item_name": "魔灵密卷",
                "limit": 1,
                "price": 400,
            },
            {
                "coin_id": 1726992,
                "id": 44,
                "item_id": 1728277,
                "item_name": "咎者焚卷",
                "limit": 1,
                "price": 400,
            },
        ]
    }

    prices = builder._parse_special_skill_shop(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    assert prices == [
        builder.ItemExchangePrice(
            source_key="special_skill_shop",
            source_name="微光秘境",
            source_entry_id=3,
            item_id=1727009,
            item_name="魔灵密卷",
            item_quantity=1,
            currency_item_id=1726992,
            amount=400,
            purchase_limit=1,
            start_time=0,
            end_time=0,
        ),
        builder.ItemExchangePrice(
            source_key="special_skill_shop",
            source_name="微光秘境",
            source_entry_id=44,
            item_id=1728277,
            item_name="咎者焚卷",
            item_quantity=1,
            currency_item_id=1726992,
            amount=400,
            purchase_limit=1,
            start_time=0,
            end_time=0,
        ),
    ]


def test_parse_effect_descriptions_keeps_named_entries() -> None:
    payload = {
        "root": {
            "item": [
                {
                    "id": 544,
                    "kind": 1,
                    "kinddes": "冥妖之悼",
                    "desc": "效果说明",
                },
                {"id": 545, "kind": 1, "kinddes": "", "desc": "忽略"},
                {"id": 546, "kind": 1, "kinddes": "无说明", "desc": ""},
                {
                    "id": 547,
                    "kind": 4,
                    "kinddes": "己方",
                    "desc": "不是专属效果",
                },
            ]
        }
    }

    rows = builder._parse_effect_descriptions(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    assert rows == [
        builder.EffectDescription(
            effect_id=544,
            name="冥妖之悼",
            description="效果说明",
        )
    ]


def test_parse_special_effect_statuses_keeps_display_name_aliases() -> None:
    payload = {
        "config": {
            "item": [
                {
                    "id": 147,
                    "dec": "旧日之晷",
                    "des": "状态说明",
                    "tips": "旧日之晷",
                    "show_monster": 4125,
                },
                {
                    "id": 148,
                    "dec": "宙变之殢",
                    "des": "另一条说明",
                    "tips": "时晷",
                    "show_monster": 0,
                },
                {"id": 0, "dec": "忽略"},
            ]
        }
    }

    rows = builder._parse_special_effect_statuses(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    assert rows == [
        builder.SpecialEffectStatus(
            status_id=147,
            name="旧日之晷",
            description="状态说明",
            show_monster_id=4125,
        ),
        builder.SpecialEffectStatus(
            status_id=148,
            name="宙变之殢",
            description="另一条说明",
            show_monster_id=0,
        ),
        builder.SpecialEffectStatus(
            status_id=148,
            name="时晷",
            description="另一条说明",
            show_monster_id=0,
        ),
    ]


def _test_png(*, alpha: int = 255) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (2, 2), (10, 20, 30, alpha)).save(output, format="PNG")
    return output.getvalue()


def test_render_effect_icon_png_uses_cached_png(monkeypatch, tmp_path) -> None:
    png_data = _test_png()
    check = builder.EffectIconAssetCheck(
        icon_id=1644,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_CACHE_DIR", tmp_path)
    cache_path = builder._effect_icon_png_cache_path(1644)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_bytes(png_data)
    monkeypatch.setattr(
        builder,
        "_download_effect_icon_asset",
        lambda _check: (_ for _ in ()).throw(AssertionError),
    )

    render = builder._render_effect_icon_png(1644, check)

    assert render.available is True
    assert render.data == png_data


def test_render_effect_icon_png_uses_sprite_export_by_default(monkeypatch) -> None:
    png_data = _test_png()
    check = builder.EffectIconAssetCheck(
        icon_id=1644,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )

    monkeypatch.setattr(builder, "_download_effect_icon_asset", lambda _: b"FWS")
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if "-swf2xml" in args:
            assert args[-2].endswith("1644.swf")
            Path(args[-1]).write_text("<swf />", encoding="utf-8")
        elif "-xml2swf" in args:
            Path(args[-1]).write_bytes(b"FWS")
        else:
            assert args[-1].endswith("icon-clean.swf")
            output_dir = Path(args[-2])
            item_dir = output_dir / "DefineSprite_6_item"
            item_dir.mkdir()
            (item_dir / "1.png").write_bytes(png_data)
        return builder.subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(builder.subprocess, "run", fake_run)
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_RENDER_JAVA_COMMAND", "java")
    monkeypatch.setattr(
        builder,
        "EFFECT_ICON_PNG_RENDER_FFDEC_JAR",
        Path("ffdec.jar"),
    )
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_RENDER_ZOOM", 6)

    render = builder._render_effect_icon_png(1644, check)

    assert render == builder.EffectIconPngRender(
        icon_id=1644,
        available=True,
        content_type="image/png",
        content_length=len(png_data),
        data=png_data,
        error="",
    )
    assert len(calls) == 3
    assert "-swf2xml" in calls[0]
    assert "-xml2swf" in calls[1]
    assert "sprite" in calls[2]


def test_render_effect_icon_png_falls_back_to_shape_export(monkeypatch) -> None:
    png_data = _test_png()
    check = builder.EffectIconAssetCheck(
        icon_id=1644,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )

    monkeypatch.setattr(builder, "_download_effect_icon_asset", lambda _: b"FWS")
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if "-swf2xml" in args:
            raise RuntimeError("sprite export unavailable")
        output_dir = Path(args[-2])
        output_dir.mkdir(exist_ok=True)
        (output_dir / "1.png").write_bytes(png_data)
        return builder.subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    render = builder._render_effect_icon_png(1644, check)

    assert render.available is True
    assert render.data == png_data
    assert len(calls) == 2
    assert "-swf2xml" in calls[0]
    assert "shape" in calls[1]


def test_render_effect_icon_png_retries_transient_verification_failure(
    monkeypatch,
) -> None:
    png_data = _test_png()
    check = builder.EffectIconAssetCheck(
        icon_id=806,
        url="https://seer.61.com/resource/effectIcon/806.swf",
        available=False,
        status=0,
        content_type="",
        content_length=None,
        error="TLS handshake timed out",
    )
    download_calls: list[builder.EffectIconAssetCheck] = []

    def fake_download(asset_check):
        download_calls.append(asset_check)
        return b"FWS"

    def fake_run(args, **_kwargs):
        (Path(args[-2]) / "1.png").write_bytes(png_data)
        return builder.subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(builder, "_download_effect_icon_asset", fake_download)
    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    render = builder._render_effect_icon_png(806, check)

    assert download_calls == [check]
    assert render.available is True
    assert render.data == png_data
    assert builder._effect_icon_runtime_asset_url(check) == check.url


def test_effect_icon_runtime_asset_url_omits_confirmed_missing_asset() -> None:
    check = builder.EffectIconAssetCheck(
        icon_id=999999,
        url="https://seer.61.com/resource/effectIcon/999999.swf",
        available=False,
        status=404,
        content_type="text/html",
        content_length=None,
        error="",
    )

    assert builder._effect_icon_runtime_asset_url(check) is None


def test_render_effect_icon_png_rejects_transparent_ffdec_output(monkeypatch) -> None:
    check = builder.EffectIconAssetCheck(
        icon_id=1644,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )
    monkeypatch.setattr(builder, "_download_effect_icon_asset", lambda _: b"FWS")

    def fake_run(args, **_kwargs):
        (Path(args[-2]) / "1.png").write_bytes(_test_png(alpha=0))
        return builder.subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    render = builder._render_effect_icon_png(1644, check)

    assert render.available is False
    assert render.data is None
    assert "fully transparent" in render.error


def test_render_composite_effect_icon_png_exports_clean_item_sprite(
    monkeypatch,
) -> None:
    check = builder.EffectIconAssetCheck(
        icon_id=613,
        url="https://example.test/613.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )
    monkeypatch.setattr(builder, "_download_effect_icon_asset", lambda _: b"FWS")
    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if "-swf2xml" in args:
            Path(args[-1]).write_text(
                """
                <swf>
                  <item type="PlaceObject3Tag"
                        placeFlagHasFilterList="true">
                    <surfaceFilterList>
                      <item type="COLORMATRIXFILTER" />
                      <item type="GLOWFILTER" />
                      <item type="BLURFILTER" />
                    </surfaceFilterList>
                  </item>
                </swf>
                """,
                encoding="utf-8",
            )
        elif "-xml2swf" in args:
            tree = builder.ET.parse(args[-2])
            filter_types = [
                node.attrib["type"]
                for node in tree.findall(".//surfaceFilterList/item")
            ]
            assert filter_types == ["BLURFILTER"]
            Path(args[-1]).write_bytes(b"FWS")
        else:
            assert args[-1].endswith("icon-clean.swf")
            output_dir = Path(args[-2])
            item_dir = output_dir / "DefineSprite_6_item"
            item_dir.mkdir()
            (item_dir / "1.png").write_bytes(_test_png())
        return builder.subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.setattr(builder.subprocess, "run", fake_run)

    render = builder._render_effect_icon_png(613, check)

    assert render.available is True
    assert render.data is not None
    assert len(calls) == 3
    assert "-swf2xml" in calls[0]
    assert "-xml2swf" in calls[1]
    assert "sprite" in calls[2]


def test_strip_effect_icon_presentation_filters_removes_empty_list(
    tmp_path,
) -> None:
    xml_path = tmp_path / "icon.xml"
    xml_path.write_text(
        """
        <swf>
          <item type="PlaceObject3Tag" placeFlagHasFilterList="true">
            <surfaceFilterList>
              <item type="COLORMATRIXFILTER" />
              <item type="GLOWFILTER" />
            </surfaceFilterList>
          </item>
        </swf>
        """,
        encoding="utf-8",
    )

    builder._strip_effect_icon_presentation_filters(xml_path)

    item = builder.ET.parse(xml_path).find(".//item")
    assert item is not None
    assert item.attrib["placeFlagHasFilterList"] == "false"
    assert item.find("surfaceFilterList") is None


def test_parse_unity_item_names_reads_exchange_currency_names() -> None:
    payload = {
        "root": {
            "items": [
                {"id": 1726992, "name": "共振晶体"},
                {"id": 1726710, "name": "共鸣锚点"},
            ]
        }
    }

    names = builder._parse_unity_item_names(
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )

    assert names == {1726992: "共振晶体", 1726710: "共鸣锚点"}


def test_parse_pet_partner_data_keeps_badge_cost_and_skill_upgrade() -> None:
    partners = {
        "data": [
            {
                "id": 15,
                "partnerName": "源初之夜",
                "partnerMonsterId": "4329|3491",
                "cost": 8,
            }
        ]
    }
    upgrades = {
        "data": [
            {
                "monID": 4329,
                "descBefore": "强化前魂印",
                "descAfter": "强化后魂印",
                "skill": "36696",
            },
            {
                "monID": 9999,
                "descBefore": "未加入羁绊组",
                "descAfter": "未加入羁绊组",
                "skill": "1",
            },
        ]
    }

    data = builder._parse_pet_partner_data(
        json.dumps(
            {
                "schema_version": 1,
                "source": {
                    "package": "ConfigPackage",
                    "config_package_version": "test-version",
                },
                "groups": [
                    {
                        "key": partners["data"][0]["id"],
                        "type": "2",
                        "name": partners["data"][0]["partnerName"],
                        "member_pet_ids": [4329, 3491],
                        "cost": partners["data"][0]["cost"],
                    },
                    {
                        "key": 1,
                        "type": "1",
                        "name": "雷电传承",
                        "member_pet_ids": [3142, 3150],
                        "cost": 3,
                    },
                ],
                "upgrades": [
                    {
                        "pet_id": upgrade["monID"],
                        "before_description": upgrade["descBefore"],
                        "after_description": upgrade["descAfter"],
                        "skill_ids": [upgrade["skill"]],
                    }
                    for upgrade in upgrades["data"]
                ]
                + [
                    {
                        "pet_id": 3142,
                        "before_description": "强化前魂印",
                        "after_description": "强化后魂印",
                        "skill_ids": ["123"],
                    }
                ],
            },
            ensure_ascii=False,
        ).encode("utf-8")
    )

    assert data.groups == [
        builder.PetPartnerGroup(
            group_id=15,
            name="源初之夜",
            member_pet_ids=(4329, 3491),
            cost_item_id=1722827,
            cost_item_name="契约徽章",
            cost_item_quantity=8,
        )
    ]
    assert data.upgrades == [
        builder.PetPartnerUpgrade(
            pet_id=4329,
            before_description="强化前魂印",
            after_description="强化后魂印",
            skill_id=36696,
        )
    ]
    assert all(3142 not in group.member_pet_ids for group in data.groups)
    assert all(upgrade.pet_id != 3142 for upgrade in data.upgrades)


def test_merge_writes_item_exchange_prices(tmp_path) -> None:
    database = tmp_path / "ironsbot-data.sqlite"
    price = builder.ItemExchangePrice(
        source_key="battlepass_shop",
        source_name="战令商店",
        source_entry_id=1005,
        item_id=1728296,
        item_name="双源魂蒂",
        item_quantity=1,
        currency_item_id=1726710,
        currency_name="共鸣锚点",
        amount=2000,
        purchase_limit=6,
        start_time=0,
        end_time=0,
    )
    effect_description = builder.EffectDescription(
        effect_id=544,
        name="冥妖之悼",
        description="效果说明",
    )
    special_effect_status = builder.SpecialEffectStatus(
        status_id=147,
        name="旧日之晷",
        description="状态说明",
        show_monster_id=4125,
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
    pet_partner_data = builder.PetPartnerData(
        groups=[
            builder.PetPartnerGroup(
                group_id=15,
                name="源初之夜",
                member_pet_ids=(4329, 3491),
                cost_item_id=1722827,
                cost_item_name="契约徽章",
                cost_item_quantity=8,
            )
        ],
        upgrades=[
            builder.PetPartnerUpgrade(
                pet_id=4329,
                before_description="强化前魂印",
                after_description="强化后魂印",
                skill_id=36696,
            )
        ],
    )

    builder._merge_ironsbot_tables(
        database,
        config_data=config_data,
        autocard_data=autocard_data,
        item_exchange_prices=[price],
        effect_descriptions=[effect_description],
        special_effect_statuses=[special_effect_status],
        pet_partner_data=pet_partner_data,
        weekly_preview_probe={},
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT
                item_id,
                item_name,
                currency_item_id,
                currency_name,
                amount,
                purchase_limit,
                source_name
            FROM item_exchange_price
            """
        ).fetchone()
        effect_row = connection.execute(
            """
            SELECT effect_id, name, description
            FROM effect_description
            """
        ).fetchone()
        special_effect_status_row = connection.execute(
            """
            SELECT status_id, name, description, show_monster_id
            FROM special_effect_status
            """
        ).fetchone()
        partner_row = connection.execute(
            """
            SELECT group_id, name, cost_item_id, cost_item_quantity
            FROM pet_partner_group
            """
        ).fetchone()
        partner_upgrade_row = connection.execute(
            """
            SELECT pet_id, group_id, skill_id
            FROM pet_partner_upgrade
            """
        ).fetchone()
    assert row == (
        1728296,
        "双源魂蒂",
        1726710,
        "共鸣锚点",
        2000,
        6,
        "战令商店",
    )
    assert effect_row == (544, "冥妖之悼", "效果说明")
    assert special_effect_status_row == (147, "旧日之晷", "状态说明", 4125)
    assert partner_row == (15, "源初之夜", 1722827, 8)
    assert partner_upgrade_row == (4329, 15, 36696)
