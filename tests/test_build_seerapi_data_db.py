import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import struct
import sys
from typing import Any

from PIL import Image
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_seerapi_data_db.py"
)
SPEC = importlib.util.spec_from_file_location("build_seerapi_data_db", SCRIPT_PATH)
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


def _skin_asset_check(
    kind: str,
    resource_id: int,
    *,
    available: bool,
    status: int | None = None,
    error: str = "",
) -> Any:
    resolved_status = status if status is not None else (200 if available else 404)
    return builder.PetImageAssetCheck(
        kind=kind,
        resource_id=resource_id,
        url=f"https://example.invalid/{kind}/{resource_id}.png",
        available=available,
        status=resolved_status,
        content_type="image/png" if available else "text/html",
        content_length=1 if available else None,
        error=error,
    )


def test_resolve_classic_skin_images_keeps_direct_assets_and_falls_back_per_kind() -> None:
    skins = (
        builder.ClassicSkinImageSource(250, "异次元·黄金天马", 1400250),
        builder.ClassicSkinImageSource(268, "波西亚", 1400268),
        builder.ClassicSkinImageSource(538, "天道魂帝", 1400538),
        builder.ClassicSkinImageSource(734, "记忆之核", 1400734),
        builder.ClassicSkinImageSource(761, "永恒圣拳", 1400761),
    )
    pets = (
        builder.PetImageSource(3382, "天道魂帝", 3382),
        builder.PetImageSource(3197, "永恒圣拳", 3197),
    )
    checks = {
        (kind, resource_id): _skin_asset_check(
            kind,
            resource_id,
            available=available,
        )
        for kind, resource_id, available in (
            ("head", 1400250, True),
            ("body", 1400250, True),
            ("head", 1400268, True),
            ("body", 1400268, True),
            ("head", 1400538, False),
            ("body", 1400538, True),
            ("head", 1400734, True),
            ("body", 1400734, True),
            ("head", 1400761, False),
            ("body", 1400761, False),
            ("head", 3382, True),
            ("body", 3382, True),
            ("head", 3197, True),
            ("body", 3197, True),
        )
    }

    rows = builder._resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        {},
    )

    assert rows == [
        builder.SkinImageResolution(
            skin_id=250,
            head_resource_id=1400250,
            body_resource_id=1400250,
            head_resolution="direct_skin",
            body_resolution="direct_skin",
            source_pet_id=None,
        ),
        builder.SkinImageResolution(
            skin_id=268,
            head_resource_id=1400268,
            body_resource_id=1400268,
            head_resolution="direct_skin",
            body_resolution="direct_skin",
            source_pet_id=None,
        ),
        builder.SkinImageResolution(
            skin_id=538,
            head_resource_id=3382,
            body_resource_id=1400538,
            head_resolution="unique_name_source",
            body_resolution="direct_skin",
            source_pet_id=3382,
        ),
        builder.SkinImageResolution(
            skin_id=734,
            head_resource_id=1400734,
            body_resource_id=1400734,
            head_resolution="direct_skin",
            body_resolution="direct_skin",
            source_pet_id=None,
        ),
        builder.SkinImageResolution(
            skin_id=761,
            head_resource_id=3197,
            body_resource_id=3197,
            head_resolution="unique_name_source",
            body_resolution="unique_name_source",
            source_pet_id=3197,
        ),
    ]


def test_resolve_classic_skin_images_uses_content_hash_for_duplicate_names() -> None:
    skins = (
        builder.ClassicSkinImageSource(16, "皮皮", 1400016),
        builder.ClassicSkinImageSource(700, "皮皮", 1400700),
    )
    pets = (
        builder.PetImageSource(10, "皮皮", 10),
        builder.PetImageSource(3295, "皮皮", 3295),
    )
    checks = {
        (kind, resource_id): _skin_asset_check(
            kind,
            resource_id,
            available=available,
        )
        for kind, resource_id, available in (
            ("head", 1400016, False),
            ("body", 1400016, True),
            ("head", 1400700, False),
            ("body", 1400700, True),
            ("head", 10, True),
            ("body", 10, True),
            ("head", 3295, True),
            ("body", 3295, True),
        )
    }
    hashes = {
        ("body", 1400016): "same-as-10",
        ("body", 1400700): "same-as-10",
        ("body", 10): "same-as-10",
        ("body", 3295): "different",
    }

    rows = builder._resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        hashes,
    )

    assert [(row.skin_id, row.head_resource_id, row.source_pet_id) for row in rows] == [
        (16, 10, 10),
        (700, 10, 10),
    ]
    assert all(row.head_resolution == "content_verified_source" for row in rows)
    assert all(row.body_resolution == "direct_skin" for row in rows)


def test_resolve_classic_skin_images_keeps_unresolved_assets_explicit() -> None:
    skin = builder.ClassicSkinImageSource(999, "不存在的经典皮肤", 1400999)
    checks = {
        (kind, skin.resource_id): _skin_asset_check(
            kind,
            skin.resource_id,
            available=False,
        )
        for kind in builder.PET_IMAGE_ASSET_KINDS
    }

    rows = builder._resolve_classic_skin_image_resources(
        (skin,),
        (),
        checks,
        {},
    )

    assert rows == [
        builder.SkinImageResolution(
            skin_id=999,
            head_resource_id=0,
            body_resource_id=0,
            head_resolution="unresolved",
            body_resolution="unresolved",
            source_pet_id=None,
        )
    ]


def test_resolve_classic_skin_images_keeps_transient_failures_unverified() -> None:
    skin = builder.ClassicSkinImageSource(538, "天道魂帝", 1400538)
    source = builder.PetImageSource(3382, "天道魂帝", 3382)
    checks = {
        ("head", 1400538): _skin_asset_check(
            "head",
            1400538,
            available=False,
            status=0,
            error="timed out",
        ),
        ("body", 1400538): _skin_asset_check("body", 1400538, available=True),
        ("head", 3382): _skin_asset_check("head", 3382, available=True),
        ("body", 3382): _skin_asset_check("body", 3382, available=True),
    }

    rows = builder._resolve_classic_skin_image_resources(
        (skin,),
        (source,),
        checks,
        {},
    )

    assert rows == [
        builder.SkinImageResolution(
            skin_id=538,
            head_resource_id=0,
            body_resource_id=1400538,
            head_resolution="unverified",
            body_resolution="direct_skin",
            source_pet_id=None,
        )
    ]


def test_verify_pet_image_asset_retries_transient_failures(monkeypatch) -> None:
    attempts = iter(
        [
            _skin_asset_check(
                "body",
                1400538,
                available=False,
                status=0,
                error="timed out",
            ),
            _skin_asset_check("body", 1400538, available=True),
        ]
    )
    monkeypatch.setattr(
        builder,
        "_probe_pet_image_asset_range",
        lambda *args, **kwargs: next(attempts),
    )
    monkeypatch.setattr(builder, "HTTP_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(builder, "HTTP_RETRY_BACKOFF_SECONDS", 0)

    check = builder._verify_pet_image_asset("body", 1400538)

    assert check.available
    assert check.status == 200


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


def test_parse_autocard_season_effects() -> None:
    def text(value: str) -> bytes:
        encoded = value.encode()
        return struct.pack("<H", len(encoded)) + encoded

    payload = b"".join(
        (
            b"\x01",
            struct.pack("<i", 1),
            text("50044"),
            text("50044"),
            text("3_1"),
            struct.pack("<iii", 1, 3, 2),
            text("霁天"),
            text("每个商店阶段前3次购买价格减少1枚金币"),
            struct.pack("<iiiii", 10, 5, 0, 1, 1),
        )
    )

    assert builder._parse_autocard_season_effects(payload) == [
        builder.AutocardSeasonEffect(
            effect_id=10,
            sanctuary_id=2,
            name="霁天",
            description="每个商店阶段前3次购买价格减少1枚金币",
            buff_id="50044",
            buff_param="3_1",
            count_buff_id="50044",
            count_type=1,
            count_num=3,
            unlock_round=5,
            pic_id=0,
            season_id=1,
            stage=1,
        )
    ]


def _test_png(
    *,
    alpha: int = 255,
    size: tuple[int, int] = (2, 2),
) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", size, (10, 20, 30, alpha)).save(output, format="PNG")
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
    builder._save_effect_icon_png_cache(1644, png_data, check)
    monkeypatch.setattr(
        builder,
        "_download_effect_icon_asset",
        lambda _check: (_ for _ in ()).throw(AssertionError),
    )

    render = builder._render_effect_icon_png(1644, check)

    assert render.available is True
    assert render.data == png_data


def test_effect_icon_cache_is_invalidated_when_source_size_changes(
    monkeypatch,
    tmp_path,
) -> None:
    icon_id = 1644
    check = builder.EffectIconAssetCheck(
        icon_id=icon_id,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )
    changed_check = builder.replace(check, content_length=124)
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_CACHE_DIR", tmp_path)
    builder._save_effect_icon_png_cache(icon_id, _test_png(), check)

    assert builder._load_effect_icon_png_cache(icon_id, check) is not None
    assert builder._load_effect_icon_png_cache(icon_id, changed_check) is None


def test_effect_icon_cache_rejects_oversized_png() -> None:
    oversized_png = _test_png(
        size=(builder.EFFECT_ICON_PNG_MAX_DIMENSION + 1, 1),
    )

    with pytest.raises(ValueError, match="dimensions exceed"):
        builder._visible_png_pixel_count(oversized_png)


def test_seed_effect_icon_cache_uses_matching_renderer_version(
    monkeypatch,
    tmp_path,
) -> None:
    icon_id = 1644
    database_path = tmp_path / "previous.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE ironsbot_metadata (key TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO ironsbot_metadata VALUES (?, ?)",
            ("effect_icon_png_cache_version", builder.EFFECT_ICON_PNG_CACHE_VERSION),
        )
        connection.execute(
            """
            CREATE TABLE soulmark_icon (
                icon_id INTEGER,
                icon_png BLOB,
                icon_png_available INTEGER,
                icon_asset_content_length INTEGER,
                icon_asset_content_type TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO soulmark_icon VALUES (?, ?, 1, 123, ?)",
            (icon_id, _test_png(), "application/x-shockwave-flash"),
        )
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_CACHE_DIR", tmp_path / "cache")
    check = builder.EffectIconAssetCheck(
        icon_id=icon_id,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )

    assert builder._seed_effect_icon_png_cache_from_database(database_path) == 1
    assert builder._load_effect_icon_png_cache(icon_id, check) == _test_png()


def test_seed_effect_icon_cache_rejects_previous_renderer_version(
    monkeypatch,
    tmp_path,
) -> None:
    database_path = tmp_path / "previous.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE ironsbot_metadata (key TEXT, value TEXT)")
        connection.execute(
            "INSERT INTO ironsbot_metadata VALUES (?, ?)",
            ("effect_icon_png_cache_version", "effect-icon-png-legacy"),
        )
        connection.execute(
            """
            CREATE TABLE soulmark_icon (
                icon_id INTEGER,
                icon_png BLOB,
                icon_png_available INTEGER,
                icon_asset_content_length INTEGER,
                icon_asset_content_type TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO soulmark_icon VALUES (1644, ?, 1, 123, ?)",
            (_test_png(), "application/x-shockwave-flash"),
        )
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_CACHE_DIR", tmp_path / "cache")

    assert builder._seed_effect_icon_png_cache_from_database(database_path) == 0
    assert not builder._effect_icon_png_cache_path(1644).exists()


def test_render_effect_icon_cache_shard_uses_a_stable_partition(
    monkeypatch,
    tmp_path,
) -> None:
    config_data = type(
        "ConfigData",
        (),
        {
            "soulmark_icons": [
                builder.SoulmarkIcon(1, 1, 1, 100),
                builder.SoulmarkIcon(2, 2, 2, 101),
                builder.SoulmarkIcon(3, 3, 3, 102),
                builder.SoulmarkIcon(4, 4, 4, 103),
            ]
        },
    )()
    captured: dict[str, list[int]] = {}
    monkeypatch.setattr(builder, "_fetch_config_package_data", lambda: config_data)
    monkeypatch.setattr(
        builder,
        "_verify_effect_icon_assets",
        lambda icon_ids: {icon_id: object() for icon_id in icon_ids},
    )
    monkeypatch.setattr(
        builder,
        "_render_effect_icon_png_assets",
        lambda checks: {
            icon_id: builder.EffectIconPngRender(
                icon_id,
                True,
                "image/png",
                1,
                b"x",
                "",
            )
            for icon_id in checks
        },
    )
    monkeypatch.setattr(
        builder,
        "_export_effect_icon_png_cache_shard",
        lambda icon_ids, _output_dir: captured.setdefault("icon_ids", icon_ids) and 2,
    )

    icon_count, available_count = builder._render_effect_icon_png_cache_shard(
        shard_index=1,
        shard_count=2,
        output_dir=tmp_path,
    )

    assert captured["icon_ids"] == [101, 103]
    assert (icon_count, available_count) == (2, 2)


def test_require_cached_effect_icons_rejects_missing_pngs(monkeypatch) -> None:
    check = builder.EffectIconAssetCheck(
        icon_id=1644,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=123,
        error="",
    )
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_RENDER_ENABLED", False)
    monkeypatch.setattr(builder, "EFFECT_ICON_PNG_REQUIRE_CACHED", True)

    with pytest.raises(ValueError, match="Missing pre-rendered effect icon PNGs: 1644"):
        builder._render_effect_icon_png_assets({1644: check})


def test_effect_icon_render_defaults_allow_complex_swf_exports() -> None:
    assert builder.EFFECT_ICON_PNG_RENDER_WORKERS == 2
    assert builder.EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS >= 45
    assert builder.EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS >= 30


def test_collect_soulmark_icon_render_issues_keeps_pet_level_context() -> None:
    unavailable_asset = builder.EffectIconAssetCheck(
        icon_id=206,
        url="https://example.test/206.swf",
        available=False,
        status=404,
        content_type="text/html",
        content_length=123,
        error="HTTP Error 404: Not Found",
    )
    render_failure_asset = builder.EffectIconAssetCheck(
        icon_id=509,
        url="https://example.test/509.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=456,
        error="",
    )
    successful_asset = builder.EffectIconAssetCheck(
        icon_id=1644,
        url="https://example.test/1644.swf",
        available=True,
        status=200,
        content_type="application/x-shockwave-flash",
        content_length=789,
        error="",
    )
    issues = builder._collect_soulmark_icon_render_issues(
        [(220, 461, 0, 206), (527, 3142, 791, 509), (1, 2, 3, 1644)],
        {206: unavailable_asset, 509: render_failure_asset, 1644: successful_asset},
        {
            206: builder.EffectIconPngRender(206, False, "", None, None, "asset unavailable"),
            509: builder.EffectIconPngRender(509, False, "", None, None, "FFDec timed out"),
            1644: builder.EffectIconPngRender(1644, True, "image/png", 10, _test_png(), ""),
        },
        {461: "阿尔克", 3142: "王·雷伊"},
    )

    assert issues == [
        builder.SoulmarkIconRenderIssue(
            icon_id=206,
            soulmark_id=220,
            pet_id=461,
            pet_name="阿尔克",
            effect_id=0,
            icon_asset_status=404,
            icon_asset_error="HTTP Error 404: Not Found",
            icon_png_error="asset unavailable",
        ),
        builder.SoulmarkIconRenderIssue(
            icon_id=509,
            soulmark_id=527,
            pet_id=3142,
            pet_name="王·雷伊",
            effect_id=791,
            icon_asset_status=200,
            icon_asset_error="",
            icon_png_error="FFDec timed out",
        ),
    ]


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
    download_calls: list[object] = []

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


def test_render_effect_icon_png_exports_clean_item_sprite(
    monkeypatch,
) -> None:
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
            assert filter_types == [
                "COLORMATRIXFILTER",
                "GLOWFILTER",
                "BLURFILTER",
            ]
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


def test_normalize_effect_icon_display_tree_collapses_presentation_duplicates(
    tmp_path,
) -> None:
    xml_path = tmp_path / "icon.xml"
    xml_path.write_text(
        """
        <swf>
          <item type="DefineSpriteTag" spriteId="5">
            <subTags>
              <item type="PlaceObject2Tag"
                    characterId="1"
                    depth="2">
                <matrix scaleX="1" scaleY="1"
                        translateX="0" translateY="0" />
              </item>
              <item type="PlaceObject3Tag"
                    characterId="3"
                    depth="3"
                    blendMode="8"
                    placeFlagHasBlendMode="true"
                    placeFlagHasColorTransform="false"
                    placeFlagHasFilterList="true">
                <matrix scaleX="0.6" scaleY="0.6"
                        translateX="-480" translateY="-600" />
                <surfaceFilterList>
                  <item type="BLURFILTER" />
                </surfaceFilterList>
              </item>
              <item type="PlaceObject2Tag"
                    characterId="4"
                    depth="7">
                <matrix scaleX="1" scaleY="1"
                        translateX="0" translateY="0" />
              </item>
              <item type="PlaceObject3Tag"
                    characterId="3"
                    depth="8"
                    blendMode="8"
                    placeFlagHasBlendMode="true"
                    placeFlagHasColorTransform="true"
                    placeFlagHasFilterList="true">
                <matrix scaleX="0.4" scaleY="0.4"
                        translateX="-320" translateY="-400" />
                <colorTransform alphaMultTerm="154" />
                <surfaceFilterList>
                  <item type="BLURFILTER" />
                </surfaceFilterList>
              </item>
            </subTags>
          </item>
        </swf>
        """,
        encoding="utf-8",
    )

    builder._normalize_effect_icon_display_tree(xml_path)

    tree = builder.ET.parse(xml_path)
    placements = tree.findall(".//subTags/item")
    character_ids = [node.attrib["characterId"] for node in placements]
    assert character_ids == ["1", "3", "4"]
    foreground = next(
        node for node in placements if node.attrib["characterId"] == "3"
    )
    assert foreground.attrib["depth"] == "8"
    assert foreground.attrib["placeFlagHasBlendMode"] == "false"
    assert foreground.attrib["placeFlagHasColorTransform"] == "false"
    assert foreground.attrib["placeFlagHasFilterList"] == "false"
    assert foreground.find("colorTransform") is None
    assert foreground.find("surfaceFilterList") is None
    matrix = foreground.find("matrix")
    assert matrix is not None
    assert matrix.attrib["scaleX"] == "0.6"


def test_normalize_effect_icon_display_tree_keeps_distinct_placements(
    tmp_path,
) -> None:
    xml_path = tmp_path / "icon.xml"
    xml_path.write_text(
        """
        <swf>
          <item type="DefineSpriteTag" spriteId="5">
            <subTags>
              <item type="PlaceObject3Tag"
                    characterId="3"
                    depth="1"
                    placeFlagHasBlendMode="true"
                    placeFlagHasColorTransform="false"
                    placeFlagHasFilterList="false">
                <matrix scaleX="1" scaleY="1"
                        translateX="0" translateY="0" />
              </item>
              <item type="PlaceObject3Tag"
                    characterId="3"
                    depth="2"
                    placeFlagHasBlendMode="true"
                    placeFlagHasColorTransform="false"
                    placeFlagHasFilterList="false">
                <matrix scaleX="1" scaleY="1"
                        translateX="1000" translateY="0" />
              </item>
            </subTags>
          </item>
        </swf>
        """,
        encoding="utf-8",
    )

    builder._normalize_effect_icon_display_tree(xml_path)

    placements = builder.ET.parse(xml_path).findall(".//subTags/item")
    assert len(placements) == 2


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
                        # partner_contracts.json v1 has these source keys
                        # reversed; the builder normalizes them on ingest.
                        "before_description": upgrade["descAfter"],
                        "after_description": upgrade["descBefore"],
                        "skill_ids": [upgrade["skill"]],
                    }
                    for upgrade in upgrades["data"]
                ]
                + [
                    {
                        "pet_id": 3142,
                        "before_description": "强化后魂印",
                        "after_description": "强化前魂印",
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


def test_replace_autocard_roles_populates_official_schema_and_skips_npcs() -> None:
    data = builder.AutocardData(
        cards=[],
        roles=[
            {
                "id": 1,
                "name": "Raw role name",
                "nature": 7,
                "health": 99,
                "skillName": "Raw skill name",
                "skillTxt": "Raw skill text",
                "skillUpgrade": "Raw upgrade",
                "desc": "Raw description",
            },
            {
                "id": 10001,
                "name": "NPC role excluded by the official analyzer",
                "nature": 8,
                "health": 88,
            },
        ],
        natures=[
            {"id": 7, "name": "Ground"},
            {"id": 999, "name": "None"},
        ],
        buffs=[],
        source="test-source",
    )

    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            """
            CREATE TABLE autocard_element_type (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE autocard_role (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                health INTEGER NOT NULL,
                skill_desc TEXT NOT NULL,
                is_passive_skill BOOLEAN NOT NULL,
                skill_cost INTEGER,
                skill_game_limit INTEGER,
                skill_round_limit INTEGER,
                element_type_id INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO autocard_role (
                id,
                name,
                description,
                health,
                skill_desc,
                is_passive_skill,
                skill_cost,
                skill_game_limit,
                skill_round_limit,
                element_type_id
            )
            VALUES (1, 'Official role', 'Official description', 42,
                    'Official skill description', 0, 3, 4, 5, 6)
            """
        )

        builder._replace_autocard_role_table(connection, data, 123.0)
        builder._replace_autocard_role_table(connection, data, 456.0)

        rows = connection.execute(
            """
            SELECT
                id,
                name,
                description,
                health,
                skill_desc,
                is_passive_skill,
                skill_cost,
                skill_game_limit,
                skill_round_limit,
                element_type_id,
                nature,
                skill_name,
                skill_text,
                skill_upgrade,
                raw_json,
                source,
                updated_at
            FROM autocard_role
            ORDER BY id
            """
        ).fetchall()
        element_types = connection.execute(
            "SELECT id, name FROM autocard_element_type ORDER BY id"
        ).fetchall()

    assert len(rows) == 1
    assert rows[0][:14] == (
        1,
        "Raw role name",
        "Raw description",
        99,
        "Raw skill text",
        1,
        None,
        None,
        None,
        7,
        7,
        "Raw skill name",
        "Raw skill text",
        "Raw upgrade",
    )
    assert json.loads(rows[0][14]) == data.roles[0]
    assert rows[0][15:] == ("test-source", 456.0)
    assert element_types == [(7, "Ground"), (999, "None")]


def test_merge_writes_item_exchange_prices(tmp_path) -> None:
    database = tmp_path / "seerapi-data.sqlite"
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
        autocard_season_effects=[
            builder.AutocardSeasonEffect(
                effect_id=10,
                sanctuary_id=2,
                name="霁天",
                description="每个商店阶段前3次购买价格减少1枚金币",
                buff_id="50044",
                buff_param="3_1",
                count_buff_id="50044",
                count_type=1,
                count_num=3,
                unlock_round=5,
                pic_id=0,
                season_id=1,
                stage=1,
            )
        ],
    )
    autocard_data = builder.AutocardData(
        cards=[],
        roles=[],
        natures=[],
        buffs=[
            {
                "id": 50073,
                "object": "赛季效果",
                "param": "a",
                "paramDes": (
                    "游戏开始时，前排最左侧和最右侧位置变为【沃土】，"
                    "初始养分计数为1"
                ),
                "IsDeathEffect": 0,
                "IsPlaceEffect": 0,
                "effectIcon": "",
            }
        ],
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
        skin_image_resolutions=[
            builder.SkinImageResolution(
                skin_id=538,
                head_resource_id=3382,
                body_resource_id=1400538,
                head_resolution="unique_name_source",
                body_resolution="direct_skin",
                source_pet_id=3382,
            )
        ],
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
        skin_image_row = connection.execute(
            """
            SELECT
                skin_id,
                head_resource_id,
                body_resource_id,
                head_resolution,
                body_resolution,
                source_pet_id
            FROM skin_image_resolution
            """
        ).fetchone()
        autocard_buff_row = connection.execute(
            """
            SELECT
                id,
                object,
                param,
                param_description,
                is_death_effect,
                is_place_effect,
                effect_icon
            FROM autocard_buff
            """
        ).fetchone()
        autocard_season_effect_row = connection.execute(
            """
            SELECT
                id,
                sanctuary_id,
                name,
                description,
                buff_id,
                buff_param,
                unlock_round,
                stage
            FROM autocard_season_effect
            """
        ).fetchone()
        icon_issue_count = connection.execute(
            "SELECT COUNT(*) FROM soulmark_icon_render_issue"
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
    assert skin_image_row == (
        538,
        3382,
        1400538,
        "unique_name_source",
        "direct_skin",
        3382,
    )
    assert autocard_buff_row == (
        50073,
        "赛季效果",
        "a",
        "游戏开始时，前排最左侧和最右侧位置变为【沃土】，初始养分计数为1",
        0,
        0,
        "",
    )
    assert autocard_season_effect_row == (
        10,
        2,
        "霁天",
        "每个商店阶段前3次购买价格减少1枚金币",
        "50044",
        "3_1",
        5,
        1,
    )
    assert icon_issue_count == (0,)
