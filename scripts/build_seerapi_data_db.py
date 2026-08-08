# SPDX-License-Identifier: MIT
"""Build the published SeerAPI runtime SQLite database.

IronsBot downloads this database as its main data source. The upstream SeerAPI
database is used as build input here; runtime extension fields are merged into
the final SQLite file before it is published.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DB = ROOT / os.environ.get("SEERAPI_DATA_OUTPUT", "seerapi-data.sqlite")
UPSTREAM_SEERAPI_URL = os.environ.get(
    "IRONSBOT_DATA_UPSTREAM_SEERAPI_URL",
    "https://github.com/Murmansk-Seer/api-data/releases/download/latest/seerapi-data.sqlite",
)
UPSTREAM_SEERAPI_PATH = os.environ.get("IRONSBOT_DATA_UPSTREAM_SEERAPI_PATH", "")
CONFIG_PACKAGE_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_CONFIG_PACKAGE_BASE_URL",
    "https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/",
)
PACKAGE_NAME = "ConfigPackage"
CONFIG_BUNDLE_NAME = "pgame_configs_bytes"
DEFAULT_PACKAGE_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_DEFAULT_PACKAGE_BASE_URL",
    "https://newseer.61.com/Assets/StandaloneWindows64/DefaultPackage/",
)
DEFAULT_PACKAGE_NAME = "DefaultPackage"
UNITY_EFFECT_ICON_ASSET_PREFIX = "Assets/Art/Ui/assets/effectIcon/"
UNITY_EFFECT_ICON_ASSET_SUFFIX = ".png"
UNITY_EFFECT_ICON_PNG_ENABLED = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_UNITY_PNG_ENABLED",
    "1",
).lower() not in {"0", "false", "no", "off"}
MINTMARK_BYTES_NAME = "mintmark.bytes"
SKIN_STORE_POOL_BYTES_NAME = "skinStorePool.bytes"
SKIN_SHOP_BYTES_NAME = "skin_shop.bytes"
ITEMS_TIP_BYTES_NAME = "itemsTip.bytes"
EFFECT_ICON_BYTES_NAME = "effectIcon.bytes"
AUTOCARD_SEASON_EFFECT_BYTES_NAME = "autocardSeasonEffect.bytes"
EFFECT_ICON_ASSET_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_ASSET_BASE_URL",
    "https://seer.61.com/resource/effectIcon/",
)
EFFECT_ICON_ASSET_SUFFIX = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_ASSET_SUFFIX",
    ".swf",
)
EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS", "15")
)
EFFECT_ICON_ASSET_VERIFY_WORKERS = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_EFFECT_ICON_ASSET_VERIFY_WORKERS", "16")),
)
EFFECT_ICON_PNG_RENDER_ENABLED = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_ENABLED",
    "1",
).lower() not in {"0", "false", "no", "off"}
EFFECT_ICON_PNG_REQUIRE_CACHED = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_REQUIRE_CACHED",
    "0",
).lower() in {"1", "true", "yes", "on"}
EFFECT_ICON_PNG_RENDER_JAVA_COMMAND = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_JAVA_COMMAND",
    "java",
)
EFFECT_ICON_PNG_RENDER_FFDEC_JAR = Path(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_FFDEC_JAR",
        "ffdec.jar",
    )
)
EFFECT_ICON_PNG_RENDER_ZOOM = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_ZOOM", "6")),
)
EFFECT_ICON_PNG_RENDER_TIMEOUT_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_TIMEOUT_SECONDS", "60")
)
EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS = float(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS",
        "45",
    )
)
EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS = float(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS",
        "30",
    )
)
EFFECT_ICON_PNG_RENDER_WORKERS = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_EFFECT_ICON_PNG_RENDER_WORKERS", "2")),
)
EFFECT_ICON_PNG_CACHE_VERSION = os.environ.get(
    "IRONSBOT_DATA_EFFECT_ICON_PNG_CACHE_VERSION",
    "ffdec-canonical-sprite-v2",
)
EFFECT_ICON_PNG_CACHE_DIR = Path(
    os.environ.get(
        "IRONSBOT_DATA_EFFECT_ICON_PNG_CACHE_DIR",
        str(ROOT / ".cache" / "effect-icon-png"),
    )
)
EFFECT_ICON_PNG_MAX_DIMENSION = 1024
EFFECT_ICON_DUPLICATE_ORIGIN_TOLERANCE = 40.0
EFFECT_ICON_DUPLICATE_MATRIX_TOLERANCE = 0.02
CONFIG_TEXT_ASSETS = {
    MINTMARK_BYTES_NAME,
    SKIN_STORE_POOL_BYTES_NAME,
    SKIN_SHOP_BYTES_NAME,
    ITEMS_TIP_BYTES_NAME,
    EFFECT_ICON_BYTES_NAME,
    AUTOCARD_SEASON_EFFECT_BYTES_NAME,
}
MINTMARK_QUALITY_TABLE = "mintmark_quality"
SKIN_STORE_PRICE_TABLE = "skin_store_price"
SKIN_SHOP_PRICE_TABLE = "skin_shop_price"
SKIN_ITEM_TIP_TABLE = "skin_item_tip"
ITEM_EXCHANGE_PRICE_TABLE = "item_exchange_price"
EFFECT_DESCRIPTION_TABLE = "effect_description"
SPECIAL_EFFECT_STATUS_TABLE = "special_effect_status"
SOULMARK_ICON_TABLE = "soulmark_icon"
SOULMARK_ICON_RENDER_ISSUE_TABLE = "soulmark_icon_render_issue"
SKIN_IMAGE_RESOLUTION_TABLE = "skin_image_resolution"
PET_PARTNER_GROUP_TABLE = "pet_partner_group"
PET_PARTNER_MEMBER_TABLE = "pet_partner_member"
PET_PARTNER_UPGRADE_TABLE = "pet_partner_upgrade"
AUTOCARD_CARD_TABLE = "autocard_card"
AUTOCARD_ROLE_TABLE = "autocard_role"
AUTOCARD_ROLE_RAW_TABLE = "autocard_role_raw"
AUTOCARD_NATURE_TABLE = "autocard_nature"
AUTOCARD_BUFF_TABLE = "autocard_buff"
AUTOCARD_SEASON_EFFECT_TABLE = "autocard_season_effect"
AUTOCARD_JSON_DIR = os.environ.get("IRONSBOT_DATA_AUTOCARD_JSON_DIR", "")
AUTOCARD_JSON_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_AUTOCARD_JSON_BASE_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/seer-unity-config-parser/main/json/",
)
AUTOCARD_CONTENT_FILE = "autocardContent.json"
AUTOCARD_NATURE_FILE = "autocardNature.json"
AUTOCARD_ROLE_FILE = "autocardRole.json"
AUTOCARD_BUFF_FILE = "autocardBuff.json"
WEEKLY_PREVIEW_IMAGE_URL = (
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "seer-unity-preview-img-dumper/main/img/preview.png"
)
WEEKLY_PREVIEW_SOURCE_URL = (
    "https://github.com/Murmansk-Seer/seer-unity-preview-img-dumper"
)
BATTLEPASS_SHOP_URL = os.environ.get(
    "IRONSBOT_DATA_BATTLEPASS_SHOP_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/battlepassShop.json",
)
ACTIVITY_SHOP_URL = os.environ.get(
    "IRONSBOT_DATA_ACTIVITY_SHOP_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/Activity_ShopConfig.json",
)
SPECIAL_SKILL_SHOP_URL = os.environ.get(
    "IRONSBOT_DATA_SPECIAL_SKILL_SHOP_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/spHideMovesShop.json",
)
UNITY_ITEM_CATALOG_URL = os.environ.get(
    "IRONSBOT_DATA_UNITY_ITEM_CATALOG_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/itemsOptimizeCatItems17.json",
)
EFFECT_DESCRIPTION_URL = os.environ.get(
    "IRONSBOT_DATA_EFFECT_DESCRIPTION_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/effectDes.json",
)
SPECIAL_EFFECT_STATUS_URL = os.environ.get(
    "IRONSBOT_DATA_SPECIAL_EFFECT_STATUS_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/signIconFight.json",
)
PARTNER_CONTRACTS_URL = os.environ.get(
    "IRONSBOT_DATA_PARTNER_CONTRACTS_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/partner_contracts.json",
)
PARTNER_CONTRACTS_SCHEMA_VERSION = 1
# ``partner_contracts.json`` v1 was generated with its two upgrade description
# keys reversed: ``before_description`` contains the strengthened text and
# ``after_description`` contains the original text. Normalize the source at the
# publishing boundary so every consumer of ``seerapi-data.sqlite`` sees the
# documented before/after meaning.
PARTNER_CONTRACTS_V1_DESCRIPTIONS_REVERSED = True
PET_PARTNER_UPGRADE_NORMALIZED_SOURCE = (
    "ConfigPackage/partnerEffectUpgrade.bytes#normalized-v1"
)
# ``partner.bytes`` uses two unrelated group types. Only type 2 is the
# contract/bond system paid with Contract Badges; type 1 is the elemental king
# inheritance system and has a different, currently unmodelled, currency.
PARTNER_CONTRACT_GROUP_TYPE = "2"
CONTRACT_BADGE_ITEM_ID = 1722827
CONTRACT_BADGE_ITEM_NAME = "契约徽章"
BATTLEPASS_SHOP_SOURCE_KEY = "battlepass_shop"
BATTLEPASS_SHOP_SOURCE_NAME = "战令商店"
ACTIVITY_SHOP_SOURCE_KEY = "activity_shop"
ACTIVITY_SHOP_SOURCE_NAME = "活动商店"
SPECIAL_SKILL_SHOP_SOURCE_KEY = "special_skill_shop"
SPECIAL_SKILL_SHOP_SOURCE_NAME = "微光秘境"
SIGNED_BYTE_MAX = 127
SIGNED_BYTE_MOD = 256
HTTP_TIMEOUT_SECONDS = 180
HTTP_RETRY_ATTEMPTS = int(os.environ.get("IRONSBOT_DATA_HTTP_RETRY_ATTEMPTS", "3"))
HTTP_RETRY_BACKOFF_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_HTTP_RETRY_BACKOFF_SECONDS", "2")
)
PET_IMAGE_ASSET_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_PET_IMAGE_ASSET_BASE_URL",
    "https://newseer.61.com/web/monster/",
)
PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS = float(
    os.environ.get("IRONSBOT_DATA_PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS", "15")
)
PET_IMAGE_ASSET_VERIFY_WORKERS = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_PET_IMAGE_ASSET_VERIFY_WORKERS", "8")),
)
CLASSIC_SKIN_CATEGORY_ID = 0
PET_IMAGE_ASSET_KINDS = ("head", "body")
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BundleInfo:
    name: str
    file_hash: str
    file_size: int


@dataclass(frozen=True, slots=True)
class PackageManifestData:
    bundles: tuple[BundleInfo, ...]
    assets: dict[str, BundleInfo]


@dataclass(frozen=True, slots=True)
class UnityEffectIconPngSource:
    icon_id: int
    asset_path: str
    bundle: BundleInfo
    bundle_url: str


@dataclass(frozen=True, slots=True)
class ConfigPackageData:
    version: str
    bundle_url: str
    mintmark_quality: dict[int, int]
    skin_store_prices: list["SkinStorePrice"]
    skin_shop_prices: list["SkinShopPrice"]
    skin_item_tips: dict[int, str]
    soulmark_icons: list["SoulmarkIcon"]
    autocard_season_effects: list["AutocardSeasonEffect"]


@dataclass(frozen=True, slots=True)
class SkinStorePrice:
    skin_id: int
    pool_id: int
    price: int
    original_price: int
    discount_rate: int
    selected_price: int
    ticket_id: int
    ticket_num: int
    start_time: int
    end_time: int


@dataclass(frozen=True, slots=True)
class AutocardSeasonEffect:
    effect_id: int
    sanctuary_id: int
    name: str
    description: str
    buff_id: str
    buff_param: str
    count_buff_id: str
    count_type: int
    count_num: int
    unlock_round: int
    pic_id: int
    season_id: int
    stage: int


@dataclass(frozen=True, slots=True)
class SkinShopPrice:
    skin_id: int
    resource_id: int
    card_price: int
    diamond_price: int
    original_price: int


@dataclass(frozen=True, slots=True)
class PetImageAssetCheck:
    kind: str
    resource_id: int
    url: str
    available: bool
    status: int
    content_type: str
    content_length: int | None
    error: str


@dataclass(frozen=True, slots=True)
class ClassicSkinImageSource:
    skin_id: int
    name: str
    resource_id: int


@dataclass(frozen=True, slots=True)
class PetImageSource:
    pet_id: int
    name: str
    resource_id: int


@dataclass(frozen=True, slots=True)
class SkinImageResolution:
    skin_id: int
    head_resource_id: int
    body_resource_id: int
    head_resolution: str
    body_resolution: str
    source_pet_id: int | None


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


@dataclass(frozen=True, slots=True)
class PetPartnerGroup:
    group_id: int
    name: str
    member_pet_ids: tuple[int, ...]
    cost_item_id: int
    cost_item_name: str
    cost_item_quantity: int


@dataclass(frozen=True, slots=True)
class PetPartnerUpgrade:
    pet_id: int
    before_description: str
    after_description: str
    skill_id: int | None


@dataclass(frozen=True, slots=True)
class PetPartnerData:
    groups: list[PetPartnerGroup]
    upgrades: list[PetPartnerUpgrade]


@dataclass(frozen=True, slots=True)
class SoulmarkIcon:
    soulmark_id: int
    pet_id: int
    effect_id: int
    icon_id: int


@dataclass(frozen=True, slots=True)
class EffectIconAssetCheck:
    icon_id: int
    url: str
    available: bool
    status: int
    content_type: str
    content_length: int | None
    error: str


@dataclass(frozen=True, slots=True)
class EffectIconPngRender:
    icon_id: int
    available: bool
    content_type: str
    content_length: int | None
    data: bytes | None
    error: str


@dataclass(frozen=True, slots=True)
class UnityEffectIconPngLoad:
    package_version: str
    total_manifest_icon_count: int
    sources: dict[int, UnityEffectIconPngSource]
    asset_checks: dict[int, EffectIconAssetCheck]
    png_renders: dict[int, EffectIconPngRender]


@dataclass(frozen=True, slots=True)
class EffectIconPngResolution:
    asset_checks: dict[int, EffectIconAssetCheck]
    png_renders: dict[int, EffectIconPngRender]
    unity_package_version: str
    unity_manifest_icon_count: int
    unity_png_available_count: int
    unity_missing_icon_ids: tuple[int, ...]
    swf_fallback_icon_count: int


@dataclass(frozen=True, slots=True)
class SoulmarkIconRenderIssue:
    icon_id: int
    soulmark_id: int
    pet_id: int
    pet_name: str
    effect_id: int
    icon_asset_status: int
    icon_asset_error: str
    icon_png_error: str


@dataclass(frozen=True, slots=True)
class AutocardData:
    cards: list[dict[str, object]]
    roles: list[dict[str, object]]
    natures: list[dict[str, object]]
    buffs: list[dict[str, object]]
    source: str


class BytesReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def read_bool(self) -> bool:
        value = self._data[self._pos] != 0
        self._pos += 1
        return value

    def read_i8(self) -> int:
        value = self._data[self._pos]
        self._pos += 1
        return value - SIGNED_BYTE_MOD if value > SIGNED_BYTE_MAX else value

    def read_u16(self) -> int:
        value = struct.unpack_from("<H", self._data, self._pos)[0]
        self._pos += 2
        return int(value)

    def read_u32(self) -> int:
        value = struct.unpack_from("<I", self._data, self._pos)[0]
        self._pos += 4
        return int(value)

    def read_i32(self) -> int:
        value = struct.unpack_from("<i", self._data, self._pos)[0]
        self._pos += 4
        return int(value)

    def read_i64(self) -> int:
        value = struct.unpack_from("<q", self._data, self._pos)[0]
        self._pos += 8
        return int(value)

    def read_text(self) -> str:
        length = self.read_u16()
        end = self._pos + length
        value = self._data[self._pos : end].decode("utf-8")
        self._pos = end
        return value


def _request(
    url: str,
    *,
    method: str | None = None,
    headers: dict[str, str] | None = None,
) -> Request:
    request_headers = {"User-Agent": "IronsBot data builder"}
    if headers:
        request_headers.update(headers)
    return Request(
        url,
        headers=request_headers,
        method=method,
    )


def _urlopen_with_retries(request: Request):
    attempts = max(1, HTTP_RETRY_ATTEMPTS)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return urlopen(request, timeout=HTTP_TIMEOUT_SECONDS)
        except HTTPError as e:
            last_error = e
            if e.code < 500 and e.code != 429:
                raise
        except (URLError, TimeoutError, OSError) as e:
            last_error = e

        if attempt >= attempts:
            break

        delay = HTTP_RETRY_BACKOFF_SECONDS * attempt
        logger.warning(
            "HTTP request failed (%s/%s): %s; retrying in %.1fs",
            attempt,
            attempts,
            last_error,
            delay,
        )
        time.sleep(delay)

    if last_error is not None:
        raise last_error
    raise RuntimeError("HTTP request failed without an exception")


def _download_bytes(url: str) -> bytes:
    with _urlopen_with_retries(_request(url)) as response:
        return response.read()


def _download_file(url: str, path: Path) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    with (
        _urlopen_with_retries(_request(url)) as response,
        tmp_path.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)
    tmp_path.replace(path)


def _copy_or_download_upstream_database(path: Path) -> None:
    """Populate *path* from a locally verified DB when supplied, else download."""
    if UPSTREAM_SEERAPI_PATH:
        source = Path(UPSTREAM_SEERAPI_PATH).expanduser()
        if not source.is_file():
            raise FileNotFoundError(
                "Verified upstream SeerAPI database does not exist: "
                f"{source}"
            )
        if source.resolve() != path.resolve():
            shutil.copy2(source, path)
        return
    _download_file(UPSTREAM_SEERAPI_URL, path)


def _probe_weekly_preview_image() -> dict[str, str]:
    try:
        with _urlopen_with_retries(
            _request(WEEKLY_PREVIEW_IMAGE_URL, method="HEAD")
        ) as response:
            headers = response.headers
            return {
                "weekly_preview_status": str(response.status),
                "weekly_preview_content_type": headers.get_content_type()
                or "image/png",
                "weekly_preview_content_length": headers.get(
                    "Content-Length",
                    "",
                ),
                "weekly_preview_probe_error": "",
            }
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        logger.warning("Weekly preview image probe skipped: %s", e)
        return {
            "weekly_preview_status": "",
            "weekly_preview_content_type": "",
            "weekly_preview_content_length": "",
            "weekly_preview_probe_error": str(e)[:200],
        }


def _parse_package_manifest(manifest_data: bytes) -> PackageManifestData:
    reader = BytesReader(manifest_data)
    reader.read_u32()
    reader.read_text()
    reader.read_bool()
    reader.read_bool()
    reader.read_bool()
    reader.read_i32()
    reader.read_text()
    reader.read_text()

    asset_refs: list[tuple[str, int]] = []
    asset_count = reader.read_i32()
    for _ in range(asset_count):
        asset_path = reader.read_text()
        bundle_index = reader.read_i32()
        depend_count = reader.read_u16()
        for _ in range(depend_count):
            reader.read_i32()
        asset_refs.append((asset_path, bundle_index))

    bundle_count = reader.read_i32()
    bundles: list[BundleInfo] = []
    for _ in range(bundle_count):
        name = reader.read_text()
        reader.read_u32()
        file_hash = reader.read_text()
        reader.read_text()
        file_size = reader.read_i64()
        reader.read_bool()
        reader.read_i8()
        reference_count = reader.read_u16()
        for _ in range(reference_count):
            reader.read_i32()
        bundles.append(BundleInfo(name=name, file_hash=file_hash, file_size=file_size))

    assets: dict[str, BundleInfo] = {}
    for asset_path, bundle_index in asset_refs:
        if 0 <= bundle_index < len(bundles):
            assets[asset_path] = bundles[bundle_index]

    return PackageManifestData(bundles=tuple(bundles), assets=assets)


def _find_config_bundle(manifest_data: bytes) -> BundleInfo:
    manifest = _parse_package_manifest(manifest_data)

    for bundle in manifest.bundles:
        if bundle.name == CONFIG_BUNDLE_NAME:
            return bundle

    if len(manifest.bundles) == 1:
        return manifest.bundles[0]

    raise ValueError("ConfigPackage bundle not found")


def _fetch_package_manifest(
    base_url: str,
    package_name: str,
) -> tuple[str, PackageManifestData]:
    normalized_base_url = base_url.rstrip("/") + "/"
    version_url = urljoin(
        normalized_base_url,
        f"PackageManifest_{package_name}.version",
    )
    version = _download_bytes(f"{version_url}?t={int(time.time())}").decode().strip()
    manifest_url = urljoin(
        normalized_base_url,
        f"PackageManifest_{package_name}_{version}.bytes",
    )
    manifest = _parse_package_manifest(_download_bytes(manifest_url))
    return version, manifest


def _extract_text_assets(bundle_data: bytes, wanted: set[str]) -> dict[str, bytes]:
    import UnityPy

    result: dict[str, bytes] = {}
    env = UnityPy.load(io.BytesIO(bundle_data))
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        name = str(data.m_Name)
        normalized_name = name if name.endswith(".bytes") else f"{name}.bytes"
        if normalized_name not in wanted:
            continue
        script = data.m_Script
        result[normalized_name] = (
            script
            if isinstance(script, bytes)
            else script.encode("utf-8", "surrogateescape")
        )
        if len(result) == len(wanted):
            break

    missing = wanted.difference(result)
    if missing:
        raise ValueError(
            f"ConfigPackage text assets missing: {sorted(missing)}"
        )
    return result


def _skip_optional_int_array(reader: BytesReader) -> None:
    if not reader.read_bool():
        return

    count = reader.read_i32()
    for _ in range(count):
        reader.read_i32()


def _parse_mintmark_quality_item(reader: BytesReader) -> tuple[int, int]:
    _skip_optional_int_array(reader)  # Arg
    _skip_optional_int_array(reader)  # BaseAttriValue
    reader.read_i32()  # Connect
    reader.read_text()  # Des
    reader.read_text()  # EffectDes
    _skip_optional_int_array(reader)  # ExtraAttriValue
    reader.read_i32()  # Grade
    reader.read_i32()  # Hide
    mintmark_id = reader.read_i32()  # ID
    reader.read_i32()  # Level
    reader.read_i32()  # Max
    _skip_optional_int_array(reader)  # MaxAttriValue
    reader.read_i32()  # MintmarkClass
    _skip_optional_int_array(reader)  # MonsterID
    _skip_optional_int_array(reader)  # MoveID
    quality = reader.read_i32()  # Quality
    reader.read_i32()  # Rare
    reader.read_i32()  # Rarity
    reader.read_i32()  # TotalConsume
    reader.read_i32()  # Type
    return mintmark_id, quality


def _parse_mintmark_quality_bytes(data: bytes) -> dict[int, int]:
    reader = BytesReader(data)
    if not reader.read_bool():
        return {}

    quality_map: dict[int, int] = {}
    if reader.read_bool():
        count = reader.read_i32()
        for _ in range(count):
            mintmark_id, quality = _parse_mintmark_quality_item(reader)
            if mintmark_id > 0 and quality > 0:
                quality_map[mintmark_id] = quality

    if reader.read_bool():
        class_count = reader.read_i32()
        for _ in range(class_count):
            reader.read_text()
            reader.read_i32()

    return quality_map


def _parse_skin_store_pool(data: bytes) -> list[SkinStorePrice]:
    if not data:
        return []

    reader = BytesReader(data)
    result: list[SkinStorePrice] = []
    if not reader.read_bool():
        return result

    count = reader.read_i32()
    for _ in range(count):
        reader.read_i32()
        price = reader.read_i32()
        original_price = reader.read_i32()
        discount_rate = reader.read_i32()
        end_time = reader.read_i32()
        reader.read_i32()
        selected_price = reader.read_i32()
        reader.read_i32()
        pool_id = reader.read_i32()
        reader.read_i32()
        reader.read_i32()
        reader.read_i32()
        reader.read_i32()
        skin_id = reader.read_i32()
        start_time = reader.read_i32()
        ticket_id = reader.read_i32()
        ticket_num = reader.read_i32()
        result.append(
            SkinStorePrice(
                skin_id=skin_id,
                pool_id=pool_id,
                price=price,
                original_price=original_price,
                discount_rate=discount_rate,
                selected_price=selected_price,
                ticket_id=ticket_id,
                ticket_num=ticket_num,
                start_time=start_time,
                end_time=end_time,
            )
        )

    return result


def _parse_skin_shop(data: bytes) -> list[SkinShopPrice]:
    if not data:
        return []

    reader = BytesReader(data)
    result: list[SkinShopPrice] = []
    if not reader.read_bool():
        return result
    if not reader.read_bool():
        return result
    if not reader.read_bool():
        return result

    count = reader.read_i32()
    for _ in range(count):
        reader.read_i32()
        card_price = reader.read_i32()
        diamond_price = reader.read_i32()
        skin_id = reader.read_i32()
        reader.read_i32()
        reader.read_text()
        original_price = reader.read_i32()
        reader.read_i32()
        reader.read_i32()
        if reader.read_bool():
            show_count = reader.read_i32()
            for _ in range(show_count):
                reader.read_i32()
        resource_id = reader.read_i32()
        result.append(
            SkinShopPrice(
                skin_id=skin_id,
                resource_id=resource_id,
                card_price=card_price,
                diamond_price=diamond_price,
                original_price=original_price,
            )
        )

    return result


def _parse_commodity_shop(
    data: bytes,
    *,
    source_key: str,
    source_name: str,
) -> list[ItemExchangePrice]:
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


def _parse_battlepass_shop(data: bytes) -> list[ItemExchangePrice]:
    return _parse_commodity_shop(
        data,
        source_key=BATTLEPASS_SHOP_SOURCE_KEY,
        source_name=BATTLEPASS_SHOP_SOURCE_NAME,
    )


def _parse_activity_shop(data: bytes) -> list[ItemExchangePrice]:
    return _parse_commodity_shop(
        data,
        source_key=ACTIVITY_SHOP_SOURCE_KEY,
        source_name=ACTIVITY_SHOP_SOURCE_NAME,
    )


def _parse_special_skill_shop(data: bytes) -> list[ItemExchangePrice]:
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
                source_key=SPECIAL_SKILL_SHOP_SOURCE_KEY,
                source_name=SPECIAL_SKILL_SHOP_SOURCE_NAME,
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


def _parse_effect_descriptions(data: bytes) -> list[EffectDescription]:
    raw = json.loads(data.decode("utf-8-sig"))
    root = raw.get("root")
    if not isinstance(root, dict):
        return []
    rows = root.get("item", [])
    if not isinstance(rows, list):
        return []

    result: list[EffectDescription] = []
    seen_ids: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _item_int(row, "kind") != 1:
            continue
        effect_id = _item_int(row, "id")
        name = _item_text(row, "kinddes").strip()
        description = _item_text(row, "desc").strip()
        if effect_id <= 0 or not name or not description or effect_id in seen_ids:
            continue
        seen_ids.add(effect_id)
        result.append(
            EffectDescription(
                effect_id=effect_id,
                name=name,
                description=description,
            )
        )

    return result


def _parse_special_effect_statuses(data: bytes) -> list[SpecialEffectStatus]:
    raw = json.loads(data.decode("utf-8-sig"))
    config = raw.get("config")
    if not isinstance(config, dict):
        return []
    rows = config.get("item", [])
    if not isinstance(rows, list):
        return []

    result: list[SpecialEffectStatus] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        status_id = _item_int(row, "id")
        if status_id <= 0:
            continue
        names = tuple(
            dict.fromkeys(
                name
                for name in (
                    _item_text(row, "dec").strip(),
                    _item_text(row, "tips").strip(),
                )
                if name
            )
        )
        description = _item_text(row, "des").strip()
        show_monster_id = _item_int(row, "show_monster")
        for name in names:
            key = (status_id, name)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                SpecialEffectStatus(
                    status_id=status_id,
                    name=name,
                    description=description,
                    show_monster_id=show_monster_id,
                )
            )
    return sorted(result, key=lambda item: (item.status_id, item.name))


def _parse_items_tip(data: bytes) -> dict[int, str]:
    if not data:
        return {}

    reader = BytesReader(data)
    result: dict[int, str] = {}
    if not reader.read_bool():
        return result
    if not reader.read_bool():
        return result

    count = reader.read_i32()
    for _ in range(count):
        description = reader.read_text()
        item_id = reader.read_i32()
        result[item_id] = description

    return result


def _skip_optional_text_array(reader: BytesReader) -> None:
    if not reader.read_bool():
        return

    count = reader.read_i32()
    for _ in range(count):
        reader.read_text()


def _parse_effect_icon(data: bytes) -> list[SoulmarkIcon]:
    if not data:
        return []

    reader = BytesReader(data)
    if not reader.read_bool():
        return []
    if not reader.read_bool():
        return []

    result: list[SoulmarkIcon] = []
    count = reader.read_i32()
    for _ in range(count):
        soulmark_id = reader.read_i32()
        reader.read_text()  # analyze
        reader.read_text()  # args
        reader.read_text()  # come
        _skip_optional_text_array(reader)  # des
        effect_id = reader.read_i32()
        icon_id = reader.read_i32()
        reader.read_i32()  # intensify
        reader.read_i32()  # isAdv
        _skip_optional_int_array(reader)  # kind
        reader.read_i32()  # label
        reader.read_i32()  # limitedType

        pet_ids: list[int] = []
        if reader.read_bool():
            pet_count = reader.read_i32()
            pet_ids = [reader.read_i32() for _ in range(pet_count)]

        _skip_optional_int_array(reader)  # specificId
        _skip_optional_text_array(reader)  # tag
        reader.read_i32()  # target
        reader.read_text()  # tips
        reader.read_i32()  # to
        reader.read_i32()  # type

        if soulmark_id <= 0 or icon_id <= 0:
            continue
        if not pet_ids:
            pet_ids = [0]
        result.extend(
            SoulmarkIcon(
                soulmark_id=soulmark_id,
                pet_id=pet_id,
                effect_id=effect_id,
                icon_id=icon_id,
            )
            for pet_id in pet_ids
        )

    return result


def _parse_autocard_season_effects(
    data: bytes,
) -> list[AutocardSeasonEffect]:
    """Parse the authoritative current sanctuary/effect directory."""

    if not data:
        return []

    reader = BytesReader(data)
    if not reader.read_bool():
        return []

    result: list[AutocardSeasonEffect] = []
    count = reader.read_i32()
    for _ in range(count):
        count_buff_id = reader.read_text()
        buff_id = reader.read_text()
        buff_param = reader.read_text()
        count_type = reader.read_i32()
        count_num = reader.read_i32()
        sanctuary_id = reader.read_i32()
        name = reader.read_text()
        description = reader.read_text()
        effect_id = reader.read_i32()
        unlock_round = reader.read_i32()
        pic_id = reader.read_i32()
        season_id = reader.read_i32()
        stage = reader.read_i32()
        if effect_id <= 0 or sanctuary_id <= 0 or not name:
            continue
        result.append(
            AutocardSeasonEffect(
                effect_id=effect_id,
                sanctuary_id=sanctuary_id,
                name=name,
                description=description,
                buff_id=buff_id,
                buff_param=buff_param,
                count_buff_id=count_buff_id,
                count_type=count_type,
                count_num=count_num,
                unlock_round=unlock_round,
                pic_id=pic_id,
                season_id=season_id,
                stage=stage,
            )
        )
    return result


def _pet_image_asset_url(kind: str, resource_id: int) -> str:
    if kind not in PET_IMAGE_ASSET_KINDS:
        raise ValueError(f"unsupported pet image asset kind: {kind}")
    base_url = PET_IMAGE_ASSET_BASE_URL.rstrip("/") + "/"
    return urljoin(base_url, f"{kind}/{resource_id}.png")


def _is_png_asset_content(content_type: str, header: bytes = b"") -> bool:
    normalized_content_type = content_type.lower().split(";", maxsplit=1)[0]
    return normalized_content_type == "image/png" or header.startswith(
        b"\x89PNG\r\n\x1a\n"
    )


def _probe_pet_image_asset_range(
    kind: str,
    resource_id: int,
    url: str,
    *,
    prior_error: str = "",
) -> PetImageAssetCheck:
    try:
        request = _request(url, method="GET", headers={"Range": "bytes=0-15"})
        with urlopen(request, timeout=PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get_content_type()
            content_length = _parse_content_length(response.headers.get("Content-Length"))
            header = response.read(16)
            available = response.status in (200, 206) and _is_png_asset_content(
                content_type,
                header,
            )
            return PetImageAssetCheck(
                kind=kind,
                resource_id=resource_id,
                url=url,
                available=available,
                status=response.status,
                content_type=content_type,
                content_length=content_length,
                error=(
                    ""
                    if available
                    else prior_error
                    or f"unexpected ranged response: {response.status} {content_type}"
                ),
            )
    except HTTPError as error:
        return PetImageAssetCheck(
            kind=kind,
            resource_id=resource_id,
            url=url,
            available=False,
            status=error.code,
            content_type=error.headers.get_content_type(),
            content_length=_parse_content_length(error.headers.get("Content-Length")),
            error="" if error.code == 404 else _short_error(error),
        )
    except (URLError, TimeoutError, OSError) as error:
        return PetImageAssetCheck(
            kind=kind,
            resource_id=resource_id,
            url=url,
            available=False,
            status=0,
            content_type="",
            content_length=None,
            error=prior_error or _short_error(error),
        )


def _verify_pet_image_asset(
    kind: str,
    resource_id: int,
) -> PetImageAssetCheck:
    url = _pet_image_asset_url(kind, resource_id)
    # The official static host serves reliable ranged GET responses but may
    # silently stall HEAD requests. Probe one PNG header instead of turning a
    # build into hundreds of 15-second HEAD timeouts.
    attempts = max(1, HTTP_RETRY_ATTEMPTS)
    prior_error = ""
    for attempt in range(1, attempts + 1):
        check = _probe_pet_image_asset_range(
            kind,
            resource_id,
            url,
            prior_error=prior_error,
        )
        if not _is_transient_pet_image_asset_failure(check):
            return check
        if attempt >= attempts:
            return check

        prior_error = check.error
        delay = HTTP_RETRY_BACKOFF_SECONDS * attempt
        logger.warning(
            "Classic skin image probe failed (%s/%s): %s/%s (%s); retrying in %.1fs",
            attempt,
            attempts,
            kind,
            resource_id,
            check.error or f"HTTP {check.status}",
            delay,
        )
        time.sleep(delay)
    raise AssertionError("unreachable")


def _verify_pet_image_assets(
    asset_keys: set[tuple[str, int]],
) -> dict[tuple[str, int], PetImageAssetCheck]:
    if not asset_keys:
        return {}

    logger.info(
        "Validating classic skin image assets: %s image resources",
        len(asset_keys),
    )
    checks: dict[tuple[str, int], PetImageAssetCheck] = {}
    worker_count = min(PET_IMAGE_ASSET_VERIFY_WORKERS, len(asset_keys))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_verify_pet_image_asset, kind, resource_id): (
                kind,
                resource_id,
            )
            for kind, resource_id in sorted(asset_keys)
        }
        for future in as_completed(futures):
            kind, resource_id = futures[future]
            try:
                checks[(kind, resource_id)] = future.result()
            except Exception as error:
                checks[(kind, resource_id)] = PetImageAssetCheck(
                    kind=kind,
                    resource_id=resource_id,
                    url=_pet_image_asset_url(kind, resource_id),
                    available=False,
                    status=0,
                    content_type="",
                    content_length=None,
                    error=_short_error(error),
                )
    transient_failures = [
        check
        for check in checks.values()
        if check.status == 0 or check.status >= 500
    ]
    if transient_failures:
        sample = ", ".join(
            f"{check.kind}/{check.resource_id} ({check.status}: {check.error})"
            for check in transient_failures[:5]
        )
        logger.warning(
            "Classic skin image asset verification still has transient failures; "
            "affected image kinds will remain unverified: %s",
            sample,
        )
    return checks


def _is_transient_pet_image_asset_failure(check: PetImageAssetCheck) -> bool:
    return check.status == 0 or check.status == 429 or check.status >= 500


def _is_confirmed_missing_pet_image_asset(check: PetImageAssetCheck) -> bool:
    return not check.available and not _is_transient_pet_image_asset_failure(check)


def _download_pet_image_asset_hash(check: PetImageAssetCheck) -> str | None:
    if not check.available:
        return None
    try:
        with urlopen(
            _request(check.url, method="GET"),
            timeout=PET_IMAGE_ASSET_VERIFY_TIMEOUT_SECONDS,
        ) as response:
            data = response.read()
            if response.status != 200 or not _is_png_asset_content(
                response.headers.get_content_type(),
                data[:16],
            ):
                return None
    except (HTTPError, URLError, TimeoutError, OSError):
        return None
    return hashlib.sha256(data).hexdigest()


def _source_asset_keys_for_classic_skin_fallbacks(
    skins: tuple[ClassicSkinImageSource, ...],
    pets: tuple[PetImageSource, ...],
    direct_checks: dict[tuple[str, int], PetImageAssetCheck],
) -> set[tuple[str, int]]:
    candidates_by_name: dict[str, list[PetImageSource]] = {}
    for pet in pets:
        candidates_by_name.setdefault(pet.name, []).append(pet)

    asset_keys: set[tuple[str, int]] = set()
    for skin in skins:
        missing_kinds = tuple(
            kind
            for kind in PET_IMAGE_ASSET_KINDS
            if _is_confirmed_missing_pet_image_asset(
                direct_checks[(kind, skin.resource_id)]
            )
        )
        candidates = candidates_by_name.get(skin.name, [])
        for candidate in candidates:
            asset_keys.update(
                (kind, candidate.resource_id) for kind in missing_kinds
            )
            if len(candidates) > 1 and missing_kinds:
                asset_keys.update(
                    (kind, candidate.resource_id)
                    for kind in PET_IMAGE_ASSET_KINDS
                    if direct_checks[(kind, skin.resource_id)].available
                )
    return asset_keys


def _content_hash_keys_for_classic_skin_fallbacks(
    skins: tuple[ClassicSkinImageSource, ...],
    pets: tuple[PetImageSource, ...],
    checks: dict[tuple[str, int], PetImageAssetCheck],
) -> set[tuple[str, int]]:
    candidates_by_name: dict[str, list[PetImageSource]] = {}
    for pet in pets:
        candidates_by_name.setdefault(pet.name, []).append(pet)

    asset_keys: set[tuple[str, int]] = set()
    for skin in skins:
        candidates = candidates_by_name.get(skin.name, [])
        if len(candidates) < 2:
            continue
        missing_kinds = tuple(
            kind
            for kind in PET_IMAGE_ASSET_KINDS
            if _is_confirmed_missing_pet_image_asset(
                checks[(kind, skin.resource_id)]
            )
        )
        if not missing_kinds:
            continue
        counterpart_kinds = tuple(
            kind
            for kind in PET_IMAGE_ASSET_KINDS
            if checks[(kind, skin.resource_id)].available
        )
        for counterpart_kind in counterpart_kinds:
            asset_keys.add((counterpart_kind, skin.resource_id))
            asset_keys.update(
                (counterpart_kind, candidate.resource_id)
                for candidate in candidates
                if checks.get((counterpart_kind, candidate.resource_id))
                and checks[(counterpart_kind, candidate.resource_id)].available
            )
    return asset_keys


def _resolve_classic_skin_image_resources(
    skins: tuple[ClassicSkinImageSource, ...],
    pets: tuple[PetImageSource, ...],
    checks: dict[tuple[str, int], PetImageAssetCheck],
    asset_hashes: dict[tuple[str, int], str],
) -> list[SkinImageResolution]:
    candidates_by_name: dict[str, list[PetImageSource]] = {}
    for pet in pets:
        candidates_by_name.setdefault(pet.name, []).append(pet)

    resolutions: list[SkinImageResolution] = []
    for skin in skins:
        direct_by_kind = {
            kind: checks[(kind, skin.resource_id)]
            for kind in PET_IMAGE_ASSET_KINDS
        }
        resource_ids = {
            kind: skin.resource_id if check.available else 0
            for kind, check in direct_by_kind.items()
        }
        resolution_names = {
            kind: (
                "direct_skin"
                if check.available
                else "unverified"
                if _is_transient_pet_image_asset_failure(check)
                else "unresolved"
            )
            for kind, check in direct_by_kind.items()
        }
        candidates = candidates_by_name.get(skin.name, [])
        resolved_source_ids: set[int] = set()

        for kind in PET_IMAGE_ASSET_KINDS:
            if resource_ids[kind] > 0 or resolution_names[kind] != "unresolved":
                continue
            source: PetImageSource | None = None
            resolution_name = "unresolved"
            if len(candidates) == 1:
                candidate = candidates[0]
                source_check = checks.get((kind, candidate.resource_id))
                if source_check is not None and source_check.available:
                    source = candidate
                    resolution_name = "unique_name_source"
            elif len(candidates) > 1:
                counterpart_kind = next(
                    (
                        other_kind
                        for other_kind in PET_IMAGE_ASSET_KINDS
                        if direct_by_kind[other_kind].available
                    ),
                    None,
                )
                expected_hash = (
                    asset_hashes.get((counterpart_kind, skin.resource_id))
                    if counterpart_kind is not None
                    else None
                )
                if expected_hash and counterpart_kind is not None:
                    matches = [
                        candidate
                        for candidate in candidates
                        if asset_hashes.get(
                            (counterpart_kind, candidate.resource_id)
                        )
                        == expected_hash
                        and checks.get((kind, candidate.resource_id)) is not None
                        and checks[(kind, candidate.resource_id)].available
                    ]
                    if len(matches) == 1:
                        source = matches[0]
                        resolution_name = "content_verified_source"
            if source is not None:
                resource_ids[kind] = source.resource_id
                resolution_names[kind] = resolution_name
                resolved_source_ids.add(source.pet_id)

        source_pet_id = (
            next(iter(resolved_source_ids))
            if len(resolved_source_ids) == 1
            else None
        )
        resolutions.append(
            SkinImageResolution(
                skin_id=skin.skin_id,
                head_resource_id=resource_ids["head"],
                body_resource_id=resource_ids["body"],
                head_resolution=resolution_names["head"],
                body_resolution=resolution_names["body"],
                source_pet_id=source_pet_id,
            )
        )
    return resolutions


def _build_classic_skin_image_resolutions(
    db_path: Path,
) -> list[SkinImageResolution]:
    with sqlite3.connect(db_path) as conn:
        skin_rows = conn.execute(
            """
            SELECT id, name, resource_id
            FROM pet_skin
            WHERE category_id = ?
            ORDER BY id
            """,
            (CLASSIC_SKIN_CATEGORY_ID,),
        ).fetchall()
        skins = tuple(
            ClassicSkinImageSource(
                skin_id=int(skin_id),
                name=str(name).strip(),
                resource_id=int(resource_id),
            )
            for skin_id, name, resource_id in skin_rows
            if int(resource_id) > 0 and str(name).strip()
        )
        skin_names = {skin.name for skin in skins}
        pet_rows = conn.execute(
            """
            SELECT id, name, resource_id
            FROM pet
            WHERE resource_id > 0
            ORDER BY id
            """
        ).fetchall()
        pets = tuple(
            PetImageSource(
                pet_id=int(pet_id),
                name=str(name).strip(),
                resource_id=int(resource_id),
            )
            for pet_id, name, resource_id in pet_rows
            if str(name).strip() in skin_names
        )

    direct_keys = {
        (kind, skin.resource_id)
        for skin in skins
        for kind in PET_IMAGE_ASSET_KINDS
    }
    checks = _verify_pet_image_assets(direct_keys)
    source_keys = _source_asset_keys_for_classic_skin_fallbacks(
        skins,
        pets,
        checks,
    )
    checks.update(_verify_pet_image_assets(source_keys - checks.keys()))

    hash_asset_keys = _content_hash_keys_for_classic_skin_fallbacks(
        skins,
        pets,
        checks,
    )
    asset_hashes = {
        asset_key: asset_hash
        for asset_key in hash_asset_keys
        for check in (checks[asset_key],)
        if check.available
        and (asset_hash := _download_pet_image_asset_hash(check)) is not None
    }
    resolutions = _resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        asset_hashes,
    )
    fallback_count = sum(
        1
        for resolution in resolutions
        if resolution.head_resolution != "direct_skin"
        or resolution.body_resolution != "direct_skin"
    )
    unresolved_count = sum(
        1
        for resolution in resolutions
        if resolution.head_resolution in {"unresolved", "unverified"}
        or resolution.body_resolution in {"unresolved", "unverified"}
    )
    logger.info(
        "Resolved classic skin images: %s rows, %s with fallback, %s unresolved",
        len(resolutions),
        fallback_count,
        unresolved_count,
    )
    return resolutions


def _effect_icon_asset_url(icon_id: int) -> str:
    base_url = EFFECT_ICON_ASSET_BASE_URL.rstrip("/") + "/"
    return urljoin(base_url, f"{icon_id}{EFFECT_ICON_ASSET_SUFFIX}")


def _parse_content_length(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]


def _unity_effect_icon_asset_path(icon_id: int) -> str:
    return (
        f"{UNITY_EFFECT_ICON_ASSET_PREFIX}"
        f"{icon_id}{UNITY_EFFECT_ICON_ASSET_SUFFIX}"
    )


def _unity_effect_icon_expected_url(icon_id: int) -> str:
    return (
        f"{DEFAULT_PACKAGE_BASE_URL.rstrip('/')}/"
        f"#{_unity_effect_icon_asset_path(icon_id)}"
    )


def _unity_effect_icon_source_url(source: UnityEffectIconPngSource) -> str:
    return f"{source.bundle_url}#{source.asset_path}"


def _unity_effect_icon_id_from_asset_path(asset_path: str) -> int | None:
    if not asset_path.startswith(UNITY_EFFECT_ICON_ASSET_PREFIX):
        return None
    if not asset_path.endswith(UNITY_EFFECT_ICON_ASSET_SUFFIX):
        return None
    name = asset_path[
        len(UNITY_EFFECT_ICON_ASSET_PREFIX) : -len(UNITY_EFFECT_ICON_ASSET_SUFFIX)
    ]
    if not name.isdecimal():
        return None
    return int(name)


def _unity_effect_icon_id_from_object_name(name: str) -> int | None:
    normalized = name[:-4] if name.endswith(".png") else name
    if not normalized.isdecimal():
        return None
    return int(normalized)


def _encode_unity_image_png(image: object) -> bytes:
    if image is None or not hasattr(image, "save"):
        raise ValueError("Unity object has no image data")
    if hasattr(image, "convert"):
        image = image.convert("RGBA")
    output = io.BytesIO()
    image.save(output, format="PNG")
    png_data = output.getvalue()
    _visible_png_pixel_count(png_data)
    return png_data


def _extract_unity_effect_icon_pngs(
    bundle_data: bytes,
    icon_ids: set[int],
) -> tuple[dict[int, bytes], dict[int, str]]:
    import UnityPy

    candidates: dict[int, tuple[int, bytes]] = {}
    errors: dict[int, str] = {}
    env = UnityPy.load(io.BytesIO(bundle_data))
    for obj in env.objects:
        object_type = obj.type.name
        if object_type not in {"Sprite", "Texture2D"}:
            continue
        icon_id: int | None = None
        try:
            data = obj.read()
            icon_id = _unity_effect_icon_id_from_object_name(str(data.m_Name))
            if icon_id is None or icon_id not in icon_ids:
                continue
            png_data = _encode_unity_image_png(data.image)
        except Exception as e:
            if icon_id is not None:
                errors[icon_id] = _short_error(e)
            continue
        priority = 0 if object_type == "Sprite" else 1
        existing = candidates.get(icon_id)
        if existing is None or priority < existing[0]:
            candidates[icon_id] = (priority, png_data)
    return (
        {icon_id: png_data for icon_id, (_, png_data) in candidates.items()},
        errors,
    )


def _missing_unity_effect_icon_png_load(
    icon_ids: set[int],
    *,
    error: str,
    status: int = 0,
) -> UnityEffectIconPngLoad:
    return UnityEffectIconPngLoad(
        package_version="",
        total_manifest_icon_count=0,
        sources={},
        asset_checks={
            icon_id: EffectIconAssetCheck(
                icon_id=icon_id,
                url=_unity_effect_icon_expected_url(icon_id),
                available=False,
                status=status,
                content_type="",
                content_length=None,
                error=error,
            )
            for icon_id in icon_ids
        },
        png_renders={
            icon_id: EffectIconPngRender(
                icon_id=icon_id,
                available=False,
                content_type="",
                content_length=None,
                data=None,
                error=error,
            )
            for icon_id in icon_ids
        },
    )


def _fetch_unity_effect_icon_png_sources(
    icon_ids: set[int],
) -> tuple[str, int, dict[int, UnityEffectIconPngSource]]:
    base_url = DEFAULT_PACKAGE_BASE_URL.rstrip("/") + "/"
    version, manifest = _fetch_package_manifest(base_url, DEFAULT_PACKAGE_NAME)
    all_sources: dict[int, UnityEffectIconPngSource] = {}
    for asset_path, bundle in manifest.assets.items():
        icon_id = _unity_effect_icon_id_from_asset_path(asset_path)
        if icon_id is None:
            continue
        all_sources[icon_id] = UnityEffectIconPngSource(
            icon_id=icon_id,
            asset_path=asset_path,
            bundle=bundle,
            bundle_url=urljoin(base_url, bundle.file_hash),
        )
    return (
        version,
        len(all_sources),
        {icon_id: all_sources[icon_id] for icon_id in icon_ids & all_sources.keys()},
    )


def _load_unity_effect_icon_png_assets(
    icon_ids: set[int],
) -> UnityEffectIconPngLoad:
    if not icon_ids:
        return _missing_unity_effect_icon_png_load(icon_ids, error="")
    if not UNITY_EFFECT_ICON_PNG_ENABLED:
        return _missing_unity_effect_icon_png_load(
            icon_ids,
            error="Unity effect icon PNG loading disabled",
        )

    package_version, total_icon_count, sources = _fetch_unity_effect_icon_png_sources(
        icon_ids
    )
    asset_checks: dict[int, EffectIconAssetCheck] = {}
    png_renders: dict[int, EffectIconPngRender] = {}
    missing_icon_ids = icon_ids - sources.keys()
    missing_error = "Unity DefaultPackage effectIcon PNG missing"
    for icon_id in missing_icon_ids:
        asset_checks[icon_id] = EffectIconAssetCheck(
            icon_id=icon_id,
            url=_unity_effect_icon_expected_url(icon_id),
            available=False,
            status=404,
            content_type="",
            content_length=None,
            error=missing_error,
        )
        png_renders[icon_id] = EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error=missing_error,
        )

    sources_by_bundle_url: dict[str, list[UnityEffectIconPngSource]] = {}
    for source in sources.values():
        sources_by_bundle_url.setdefault(source.bundle_url, []).append(source)

    for bundle_url, bundle_sources in sources_by_bundle_url.items():
        source_icon_ids = {source.icon_id for source in bundle_sources}
        try:
            pngs, extraction_errors = _extract_unity_effect_icon_pngs(
                _download_bytes(bundle_url),
                source_icon_ids,
            )
        except Exception as e:
            pngs = {}
            extraction_errors = {
                icon_id: _short_error(e) for icon_id in source_icon_ids
            }
        for source in bundle_sources:
            png_data = pngs.get(source.icon_id)
            source_url = _unity_effect_icon_source_url(source)
            if png_data is None:
                error = extraction_errors.get(
                    source.icon_id,
                    "Unity bundle did not contain a visible PNG",
                )
                asset_checks[source.icon_id] = EffectIconAssetCheck(
                    icon_id=source.icon_id,
                    url=source_url,
                    available=True,
                    status=200,
                    content_type="application/octet-stream",
                    content_length=source.bundle.file_size,
                    error="",
                )
                png_renders[source.icon_id] = EffectIconPngRender(
                    icon_id=source.icon_id,
                    available=False,
                    content_type="",
                    content_length=None,
                    data=None,
                    error=error,
                )
                continue
            asset_checks[source.icon_id] = EffectIconAssetCheck(
                icon_id=source.icon_id,
                url=source_url,
                available=True,
                status=200,
                content_type="image/png",
                content_length=len(png_data),
                error="",
            )
            png_renders[source.icon_id] = EffectIconPngRender(
                icon_id=source.icon_id,
                available=True,
                content_type="image/png",
                content_length=len(png_data),
                data=png_data,
                error="",
            )

    return UnityEffectIconPngLoad(
        package_version=package_version,
        total_manifest_icon_count=total_icon_count,
        sources=sources,
        asset_checks=asset_checks,
        png_renders=png_renders,
    )


def _unity_effect_icon_swf_fallback_icon_ids(icon_ids: set[int]) -> list[int]:
    if not icon_ids or not UNITY_EFFECT_ICON_PNG_ENABLED:
        return sorted(icon_ids)
    try:
        _, _, sources = _fetch_unity_effect_icon_png_sources(icon_ids)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        logger.warning(
            "Unity effect icon manifest lookup skipped; rendering SWF fallback: %s",
            _short_error(e),
        )
        return sorted(icon_ids)
    return sorted(icon_ids - sources.keys())


def _resolve_effect_icon_png_assets(
    icon_ids: set[int],
) -> EffectIconPngResolution:
    if not icon_ids:
        return EffectIconPngResolution(
            asset_checks={},
            png_renders={},
            unity_package_version="",
            unity_manifest_icon_count=0,
            unity_png_available_count=0,
            unity_missing_icon_ids=(),
            swf_fallback_icon_count=0,
        )
    try:
        unity_load = _load_unity_effect_icon_png_assets(icon_ids)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        logger.warning(
            "Unity effect icon PNG loading skipped; falling back to SWF assets: %s",
            _short_error(e),
        )
        unity_load = _missing_unity_effect_icon_png_load(
            icon_ids,
            error=f"Unity effect icon PNG loading failed: {_short_error(e)}",
        )

    unity_available_count = sum(
        1 for render in unity_load.png_renders.values() if render.available
    )
    fallback_icon_ids = {
        icon_id
        for icon_id in icon_ids
        if not unity_load.png_renders[icon_id].available
    }
    fallback_checks: dict[int, EffectIconAssetCheck] = {}
    fallback_renders: dict[int, EffectIconPngRender] = {}
    if fallback_icon_ids:
        fallback_require_any = unity_available_count == 0
        fallback_checks = _verify_effect_icon_assets(
            fallback_icon_ids,
            require_any=fallback_require_any,
        )
        fallback_renders = _render_effect_icon_png_assets(
            fallback_checks,
            require_any=fallback_require_any,
        )

    asset_checks: dict[int, EffectIconAssetCheck] = {}
    png_renders: dict[int, EffectIconPngRender] = {}
    for icon_id in icon_ids:
        unity_render = unity_load.png_renders[icon_id]
        if unity_render.available:
            asset_checks[icon_id] = unity_load.asset_checks[icon_id]
            png_renders[icon_id] = unity_render
            continue
        asset_checks[icon_id] = fallback_checks.get(
            icon_id,
            unity_load.asset_checks[icon_id],
        )
        png_renders[icon_id] = fallback_renders.get(icon_id, unity_render)

    return EffectIconPngResolution(
        asset_checks=asset_checks,
        png_renders=png_renders,
        unity_package_version=unity_load.package_version,
        unity_manifest_icon_count=unity_load.total_manifest_icon_count,
        unity_png_available_count=unity_available_count,
        unity_missing_icon_ids=tuple(sorted(fallback_icon_ids)),
        swf_fallback_icon_count=len(fallback_icon_ids),
    )


def _is_effect_icon_asset_content(
    content_type: str,
    header: bytes = b"",
) -> bool:
    normalized_content_type = content_type.lower().split(";", maxsplit=1)[0]
    return normalized_content_type in {
        "application/x-shockwave-flash",
        "application/vnd.adobe.flash.movie",
    } or header.startswith((b"CWS", b"FWS", b"ZWS"))


def _probe_effect_icon_asset_range(
    icon_id: int,
    url: str,
    *,
    prior_error: str = "",
) -> EffectIconAssetCheck:
    try:
        request = _request(url, method="GET", headers={"Range": "bytes=0-15"})
        with urlopen(
            request,
            timeout=EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS,
        ) as response:
            content_type = response.headers.get_content_type()
            content_length = _parse_content_length(
                response.headers.get("Content-Length")
            )
            header = response.read(16)
            available = response.status in (200, 206) and (
                _is_effect_icon_asset_content(content_type, header)
            )
            error = ""
            if not available:
                error = prior_error or (
                    f"unexpected ranged response: {response.status} "
                    f"{content_type}"
                )
            return EffectIconAssetCheck(
                icon_id=icon_id,
                url=url,
                available=available,
                status=response.status,
                content_type=content_type,
                content_length=content_length,
                error=error,
            )
    except HTTPError as e:
        return EffectIconAssetCheck(
            icon_id=icon_id,
            url=url,
            available=False,
            status=e.code,
            content_type=e.headers.get_content_type(),
            content_length=_parse_content_length(e.headers.get("Content-Length")),
            error="" if e.code == 404 else _short_error(e),
        )
    except (URLError, TimeoutError, OSError) as e:
        return EffectIconAssetCheck(
            icon_id=icon_id,
            url=url,
            available=False,
            status=0,
            content_type="",
            content_length=None,
            error=prior_error or _short_error(e),
        )


def _verify_effect_icon_asset(icon_id: int) -> EffectIconAssetCheck:
    url = _effect_icon_asset_url(icon_id)
    try:
        with urlopen(
            _request(url, method="HEAD"),
            timeout=EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS,
        ) as response:
            content_type = response.headers.get_content_type()
            content_length = _parse_content_length(
                response.headers.get("Content-Length")
            )
            available = (
                response.status == 200
                and (content_length is None or content_length > 0)
                and _is_effect_icon_asset_content(content_type)
            )
            if available:
                return EffectIconAssetCheck(
                    icon_id=icon_id,
                    url=url,
                    available=True,
                    status=response.status,
                    content_type=content_type,
                    content_length=content_length,
                    error="",
                )
            return _probe_effect_icon_asset_range(
                icon_id,
                url,
                prior_error=(
                    f"unexpected HEAD response: {response.status} {content_type}"
                ),
            )
    except HTTPError as e:
        if e.code in {403, 405, 501}:
            return _probe_effect_icon_asset_range(
                icon_id,
                url,
                prior_error=_short_error(e),
            )
        return EffectIconAssetCheck(
            icon_id=icon_id,
            url=url,
            available=False,
            status=e.code,
            content_type=e.headers.get_content_type(),
            content_length=_parse_content_length(e.headers.get("Content-Length")),
            error="" if e.code == 404 else _short_error(e),
        )
    except (URLError, TimeoutError, OSError) as e:
        ranged_check = _probe_effect_icon_asset_range(
            icon_id,
            url,
            prior_error=_short_error(e),
        )
        return ranged_check


def _verify_effect_icon_assets(
    icon_ids: set[int],
    *,
    require_any: bool = True,
) -> dict[int, EffectIconAssetCheck]:
    if not icon_ids:
        return {}

    logger.info(
        "Validating official effect icon assets: %s unique icons",
        len(icon_ids),
    )
    checks: dict[int, EffectIconAssetCheck] = {}
    worker_count = min(EFFECT_ICON_ASSET_VERIFY_WORKERS, len(icon_ids))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_verify_effect_icon_asset, icon_id): icon_id
            for icon_id in sorted(icon_ids)
        }
        for future in as_completed(futures):
            icon_id = futures[future]
            try:
                checks[icon_id] = future.result()
            except Exception as e:
                checks[icon_id] = EffectIconAssetCheck(
                    icon_id=icon_id,
                    url=_effect_icon_asset_url(icon_id),
                    available=False,
                    status=0,
                    content_type="",
                    content_length=None,
                    error=_short_error(e),
                )

    available_count = sum(1 for check in checks.values() if check.available)
    missing_checks = [
        check for check in checks.values() if not check.available
    ]
    if available_count == 0 and require_any:
        raise ValueError("No official effect icon assets could be verified")
    if missing_checks:
        logger.warning(
            "Effect icon asset validation missing %s/%s icons; first missing: %s",
            len(missing_checks),
            len(checks),
            ", ".join(str(check.icon_id) for check in missing_checks[:10]),
        )
    return checks


def _download_effect_icon_asset(check: EffectIconAssetCheck) -> bytes:
    with urlopen(
        _request(check.url, method="GET"),
        timeout=EFFECT_ICON_ASSET_VERIFY_TIMEOUT_SECONDS,
    ) as response:
        content_type = response.headers.get_content_type()
        data = response.read()
        if response.status != 200 or not _is_effect_icon_asset_content(
            content_type,
            data[:16],
        ):
            raise ValueError(
                f"unexpected SWF response: {response.status} {content_type}"
            )
        return data


def _effect_icon_runtime_asset_url(
    check: EffectIconAssetCheck,
) -> str | None:
    if check.available or check.status == 0:
        return check.url
    return None


def _visible_png_pixel_count(data: bytes) -> int:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("renderer output is not PNG")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if max(image.size) > EFFECT_ICON_PNG_MAX_DIMENSION:
                raise ValueError(
                    "renderer output dimensions exceed "
                    f"{EFFECT_ICON_PNG_MAX_DIMENSION}px: {image.size}"
                )
            alpha_histogram = image.convert("RGBA").getchannel("A").histogram()
    except (OSError, UnidentifiedImageError) as e:
        raise ValueError(f"renderer output is an invalid PNG: {e}") from e
    return sum(alpha_histogram[1:])


def _run_ffdec_command(
    args: list[str],
    *,
    timeout_seconds: float | None = None,
) -> None:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds or EFFECT_ICON_PNG_RENDER_TIMEOUT_SECONDS,
    )
    if completed.returncode == 0:
        return
    message = (completed.stderr or "").strip() or (
        completed.stdout or ""
    ).strip()
    raise RuntimeError(f"FFDec exited {completed.returncode}: {message}")


def _select_visible_png(
    output_dir: Path,
    *,
    prefer_item_sprite: bool = False,
) -> bytes:
    candidates: list[tuple[int, bytes, Path]] = []
    invalid_errors: list[str] = []
    for png_path in sorted(output_dir.rglob("*.png")):
        png_data = png_path.read_bytes()
        try:
            visible_pixels = _visible_png_pixel_count(png_data)
        except ValueError as e:
            invalid_errors.append(f"{png_path.name}: {e}")
            continue
        if visible_pixels > 0:
            candidates.append((visible_pixels, png_data, png_path))
        else:
            invalid_errors.append(f"{png_path.name}: fully transparent")
    if prefer_item_sprite:
        item_candidates = [
            candidate
            for candidate in candidates
            if any(part.endswith("_item") for part in candidate[2].parts)
        ]
        if item_candidates:
            candidates = item_candidates
    if not candidates:
        details = "; ".join(invalid_errors[:5]) or "no PNG files exported"
        raise ValueError(f"FFDec produced no visible PNG: {details}")
    _, png_data, _ = max(
        candidates,
        key=lambda candidate: (candidate[0], len(candidate[1])),
    )
    return png_data


def _normalize_effect_icon_png(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as image:
            rgba = image.convert("RGBA")
            bounds = rgba.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError("renderer output is fully transparent")
            cropped = rgba.crop(bounds)
            side = max(cropped.size)
            normalized = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            normalized.alpha_composite(
                cropped,
                (
                    (side - cropped.width) // 2,
                    (side - cropped.height) // 2,
                ),
            )
            output = io.BytesIO()
            normalized.save(output, format="PNG")
    except (OSError, UnidentifiedImageError) as e:
        raise ValueError(f"renderer output is an invalid PNG: {e}") from e
    return output.getvalue()


def _effect_icon_matrix_value(
    matrix: ET.Element | None,
    name: str,
    default: float,
) -> float:
    if matrix is None:
        return default
    return float(matrix.attrib.get(name, default))


def _effect_icon_placement_area_scale(node: ET.Element) -> float:
    matrix = node.find("matrix")
    scale_x = _effect_icon_matrix_value(matrix, "scaleX", 1.0)
    scale_y = _effect_icon_matrix_value(matrix, "scaleY", 1.0)
    skew_x = _effect_icon_matrix_value(matrix, "rotateSkew0", 0.0)
    skew_y = _effect_icon_matrix_value(matrix, "rotateSkew1", 0.0)
    return abs(scale_x * scale_y - skew_x * skew_y)


def _effect_icon_normalized_matrix(node: ET.Element) -> tuple[float, ...]:
    matrix = node.find("matrix")
    values = (
        _effect_icon_matrix_value(matrix, "scaleX", 1.0),
        _effect_icon_matrix_value(matrix, "rotateSkew1", 0.0),
        _effect_icon_matrix_value(matrix, "rotateSkew0", 0.0),
        _effect_icon_matrix_value(matrix, "scaleY", 1.0),
    )
    magnitude = sum(value * value for value in values) ** 0.5
    if magnitude <= 1e-9:
        return values
    return tuple(value / magnitude for value in values)


def _effect_icon_normalized_origin(node: ET.Element) -> tuple[float, float]:
    matrix = node.find("matrix")
    scale_x = _effect_icon_matrix_value(matrix, "scaleX", 1.0)
    scale_y = _effect_icon_matrix_value(matrix, "scaleY", 1.0)
    translate_x = _effect_icon_matrix_value(matrix, "translateX", 0.0)
    translate_y = _effect_icon_matrix_value(matrix, "translateY", 0.0)
    return (
        translate_x / max(abs(scale_x), 1e-9),
        translate_y / max(abs(scale_y), 1e-9),
    )


def _effect_icon_has_presentation_effect(node: ET.Element) -> bool:
    return any(
        node.attrib.get(flag) == "true"
        for flag in (
            "placeFlagHasBlendMode",
            "placeFlagHasColorTransform",
            "placeFlagHasFilterList",
        )
    )


def _effect_icon_placements_share_visual_origin(
    nodes: list[ET.Element],
) -> bool:
    origins = [_effect_icon_normalized_origin(node) for node in nodes]
    matrices = [_effect_icon_normalized_matrix(node) for node in nodes]
    origin_x = [origin[0] for origin in origins]
    origin_y = [origin[1] for origin in origins]
    if (
        max(origin_x) - min(origin_x)
        > EFFECT_ICON_DUPLICATE_ORIGIN_TOLERANCE
        or max(origin_y) - min(origin_y)
        > EFFECT_ICON_DUPLICATE_ORIGIN_TOLERANCE
    ):
        return False
    first_matrix = matrices[0]
    return all(
        max(
            abs(left - right)
            for left, right in zip(first_matrix, matrix, strict=True)
        )
        <= EFFECT_ICON_DUPLICATE_MATRIX_TOLERANCE
        for matrix in matrices[1:]
    )


def _clear_effect_icon_presentation(node: ET.Element) -> None:
    for child in list(node):
        if child.tag in {"colorTransform", "surfaceFilterList"}:
            node.remove(child)
    for flag in (
        "placeFlagHasBlendMode",
        "placeFlagHasColorTransform",
        "placeFlagHasFilterList",
    ):
        if flag in node.attrib:
            node.set(flag, "false")
    if node.attrib.get("type") == "PlaceObject3Tag":
        node.set("blendMode", "0")


def _collapse_effect_icon_presentation_duplicates(
    tree: ET.ElementTree[ET.Element[str]],
) -> None:
    # Effect icons often place the same symbol several times at one visual
    # origin to build blur/glow layers. Keep one crisp representative while
    # preserving genuinely repeated symbols at different positions.
    for sprite in tree.iter("item"):
        if sprite.attrib.get("type") != "DefineSpriteTag":
            continue
        sub_tags = sprite.find("subTags")
        if sub_tags is None:
            continue
        placements_by_character: dict[str, list[ET.Element]] = {}
        for node in sub_tags:
            character_id = node.attrib.get("characterId")
            if (
                character_id
                and node.attrib.get("type", "").startswith("PlaceObject")
            ):
                placements_by_character.setdefault(character_id, []).append(
                    node
                )
        for nodes in placements_by_character.values():
            if (
                len(nodes) < 2
                or not any(
                    _effect_icon_has_presentation_effect(node)
                    for node in nodes
                )
                or not _effect_icon_placements_share_visual_origin(nodes)
            ):
                continue
            plain_nodes = [
                node
                for node in nodes
                if not _effect_icon_has_presentation_effect(node)
            ]
            canonical = max(
                plain_nodes or nodes,
                key=_effect_icon_placement_area_scale,
            )
            canonical.set(
                "depth",
                str(max(int(node.attrib.get("depth", "0")) for node in nodes)),
            )
            _clear_effect_icon_presentation(canonical)
            for node in nodes:
                if node is not canonical:
                    sub_tags.remove(node)


def _normalize_effect_icon_display_tree(xml_path: Path) -> None:
    tree = ET.parse(xml_path)
    _collapse_effect_icon_presentation_duplicates(tree)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)


def _render_full_effect_icon_png(
    swf_path: Path,
    temp_path: Path,
) -> bytes:
    xml_path = temp_path / "icon.xml"
    cleaned_swf_path = temp_path / "icon-clean.swf"
    output_dir = temp_path / "sprites"
    output_dir.mkdir()
    _run_ffdec_command(
        [
            EFFECT_ICON_PNG_RENDER_JAVA_COMMAND,
            "-jar",
            str(EFFECT_ICON_PNG_RENDER_FFDEC_JAR),
            "-swf2xml",
            str(swf_path),
            str(xml_path),
        ],
        timeout_seconds=EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS,
    )
    _normalize_effect_icon_display_tree(xml_path)
    _run_ffdec_command(
        [
            EFFECT_ICON_PNG_RENDER_JAVA_COMMAND,
            "-jar",
            str(EFFECT_ICON_PNG_RENDER_FFDEC_JAR),
            "-xml2swf",
            str(xml_path),
            str(cleaned_swf_path),
        ],
        timeout_seconds=EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS,
    )
    _run_ffdec_command(
        [
            EFFECT_ICON_PNG_RENDER_JAVA_COMMAND,
            "-jar",
            str(EFFECT_ICON_PNG_RENDER_FFDEC_JAR),
            "-zoom",
            str(EFFECT_ICON_PNG_RENDER_ZOOM),
            "-ignorebackground",
            "-format",
            "sprite:png",
            "-export",
            "sprite",
            str(output_dir),
            str(cleaned_swf_path),
        ],
        timeout_seconds=EFFECT_ICON_PNG_COMPOSITE_RENDER_TIMEOUT_SECONDS,
    )
    return _normalize_effect_icon_png(
        _select_visible_png(output_dir, prefer_item_sprite=True)
    )


def _render_shape_effect_icon_png(
    swf_path: Path,
    temp_path: Path,
) -> bytes:
    output_dir = temp_path / "shapes"
    output_dir.mkdir()
    _run_ffdec_command(
        [
            EFFECT_ICON_PNG_RENDER_JAVA_COMMAND,
            "-jar",
            str(EFFECT_ICON_PNG_RENDER_FFDEC_JAR),
            "-zoom",
            str(EFFECT_ICON_PNG_RENDER_ZOOM),
            "-format",
            "shape:png",
            "-export",
            "shape",
            str(output_dir),
            str(swf_path),
        ],
        timeout_seconds=EFFECT_ICON_PNG_SHAPE_RENDER_TIMEOUT_SECONDS,
    )
    return _normalize_effect_icon_png(_select_visible_png(output_dir))


def _render_effect_icon_png(
    icon_id: int,
    check: EffectIconAssetCheck,
) -> EffectIconPngRender:
    cached_png = _load_effect_icon_png_cache(icon_id, check)
    if cached_png is not None:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=True,
            content_type="image/png",
            content_length=len(cached_png),
            data=cached_png,
            error="",
        )
    if not EFFECT_ICON_PNG_RENDER_ENABLED:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error="PNG rendering disabled",
        )
    if not check.available and check.status != 0:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error=check.error or "SWF asset unavailable",
        )

    try:
        swf_data = _download_effect_icon_asset(check)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            swf_path = temp_path / f"{icon_id}.swf"
            swf_path.write_bytes(swf_data)
            try:
                png_data = _render_full_effect_icon_png(
                    swf_path,
                    temp_path,
                )
            except (
                ET.ParseError,
                OSError,
                subprocess.SubprocessError,
                ValueError,
                RuntimeError,
            ) as full_render_error:
                logger.warning(
                    "Full effect icon render failed for %s; "
                    "falling back to shape export: %s",
                    icon_id,
                    _short_error(full_render_error),
                )
                png_data = _render_shape_effect_icon_png(swf_path, temp_path)
        _save_effect_icon_png_cache(icon_id, png_data, check)
        return EffectIconPngRender(
            icon_id=icon_id,
            available=True,
            content_type="image/png",
            content_length=len(png_data),
            data=png_data,
            error="",
        )
    except (
        ET.ParseError,
        OSError,
        subprocess.SubprocessError,
        ValueError,
        RuntimeError,
    ) as e:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error=_short_error(e),
        )


def _effect_icon_png_cache_path(icon_id: int) -> Path:
    return (
        EFFECT_ICON_PNG_CACHE_DIR
        / EFFECT_ICON_PNG_CACHE_VERSION
        / f"{icon_id}-sprite-z{EFFECT_ICON_PNG_RENDER_ZOOM}.png"
    )


def _effect_icon_png_cache_metadata_path(icon_id: int) -> Path:
    return _effect_icon_png_cache_path(icon_id).with_suffix(".json")


def _effect_icon_png_cache_matches_asset(
    icon_id: int,
    check: EffectIconAssetCheck,
) -> bool:
    metadata_path = _effect_icon_png_cache_metadata_path(icon_id)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        logger.debug(
            "Effect icon PNG cache metadata is unavailable for %s: %s",
            icon_id,
            _short_error(error),
        )
        return False

    if not isinstance(metadata, dict):
        return False
    cached_length = metadata.get("asset_content_length")
    if not isinstance(cached_length, int) or check.content_length is None:
        return False
    return cached_length == check.content_length


def _load_effect_icon_png_cache(
    icon_id: int,
    check: EffectIconAssetCheck,
) -> bytes | None:
    path = _effect_icon_png_cache_path(icon_id)
    if not path.is_file():
        return None
    if not _effect_icon_png_cache_matches_asset(icon_id, check):
        return None
    try:
        data = path.read_bytes()
        _visible_png_pixel_count(data)
    except (OSError, ValueError) as e:
        logger.warning(
            "Ignoring invalid cached effect icon PNG %s: %s",
            path,
            _short_error(e),
        )
        return None
    return data


def _save_effect_icon_png_cache(
    icon_id: int,
    data: bytes,
    check: EffectIconAssetCheck,
) -> bool:
    try:
        _visible_png_pixel_count(data)
        path = _effect_icon_png_cache_path(icon_id)
        metadata_path = _effect_icon_png_cache_metadata_path(icon_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        temp_path = Path(temp_name)
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        temp_path.replace(path)
        metadata = json.dumps(
            {
                "asset_content_length": check.content_length,
                "icon_id": icon_id,
                "renderer_version": EFFECT_ICON_PNG_CACHE_VERSION,
            },
            sort_keys=True,
        )
        metadata_path.write_text(metadata, encoding="utf-8")
        return True
    except (OSError, ValueError) as e:
        logger.warning(
            "Failed to cache effect icon PNG %s: %s",
            icon_id,
            _short_error(e),
        )
        return False


def _render_effect_icon_png_assets(
    checks: dict[int, EffectIconAssetCheck],
    *,
    require_any: bool = True,
) -> dict[int, EffectIconPngRender]:
    if not checks:
        return {}
    renderable_checks = [
        check for check in checks.values() if check.available or check.status == 0
    ]
    if EFFECT_ICON_PNG_RENDER_ENABLED and renderable_checks:
        if shutil.which(EFFECT_ICON_PNG_RENDER_JAVA_COMMAND) is None:
            raise FileNotFoundError(
                f"Java command not found: {EFFECT_ICON_PNG_RENDER_JAVA_COMMAND}"
            )
        if not EFFECT_ICON_PNG_RENDER_FFDEC_JAR.is_file():
            raise FileNotFoundError(
                f"FFDec jar not found: {EFFECT_ICON_PNG_RENDER_FFDEC_JAR}"
            )

    logger.info(
        "Rendering official effect icon PNGs: %s unique icons",
        len(checks),
    )
    renders: dict[int, EffectIconPngRender] = {}
    worker_count = min(EFFECT_ICON_PNG_RENDER_WORKERS, len(checks))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_render_effect_icon_png, icon_id, check): icon_id
            for icon_id, check in sorted(checks.items())
        }
        completed_count = 0
        for future in as_completed(futures):
            icon_id = futures[future]
            try:
                renders[icon_id] = future.result()
            except Exception as e:
                renders[icon_id] = EffectIconPngRender(
                    icon_id=icon_id,
                    available=False,
                    content_type="",
                    content_length=None,
                    data=None,
                    error=_short_error(e),
                )
            completed_count += 1
            if completed_count % 20 == 0 or completed_count == len(futures):
                available_count = sum(
                    1 for render in renders.values() if render.available
                )
                logger.info(
                    "Effect icon PNG render progress: %s/%s completed, "
                    "%s available",
                    completed_count,
                    len(futures),
                    available_count,
                )

    available_count = sum(1 for render in renders.values() if render.available)
    if EFFECT_ICON_PNG_REQUIRE_CACHED:
        missing_icon_ids = [
            icon_id
            for icon_id, check in checks.items()
            if (check.available or check.status == 0)
            and not renders[icon_id].available
        ]
        if missing_icon_ids:
            preview = ", ".join(str(icon_id) for icon_id in missing_icon_ids[:10])
            raise ValueError(
                "Missing pre-rendered effect icon PNGs: "
                f"{preview}"
                + (" ..." if len(missing_icon_ids) > 10 else "")
            )
    if EFFECT_ICON_PNG_RENDER_ENABLED and available_count == 0 and require_any:
        first_errors = "; ".join(
            render.error
            for render in list(renders.values())[:5]
            if render.error
        )
        raise ValueError(
            "FFDec did not render any visible effect icon PNGs"
            + (f": {first_errors}" if first_errors else "")
        )
    logger.info(
        "Rendered official effect icon PNGs: %s/%s available",
        available_count,
        len(renders),
    )
    return renders


def _collect_soulmark_icon_render_issues(
    soulmark_icons: list[tuple[int, int, int, int]],
    asset_checks: dict[int, EffectIconAssetCheck],
    png_renders: dict[int, EffectIconPngRender],
    pet_names: dict[int, str],
) -> list[SoulmarkIconRenderIssue]:
    """Return every pet/soulmark whose verified icon did not yield a PNG."""
    issues: list[SoulmarkIconRenderIssue] = []
    for soulmark_id, pet_id, effect_id, icon_id in soulmark_icons:
        png_render = png_renders[icon_id]
        if png_render.available:
            continue
        asset_check = asset_checks[icon_id]
        issues.append(
            SoulmarkIconRenderIssue(
                icon_id=icon_id,
                soulmark_id=soulmark_id,
                pet_id=pet_id,
                pet_name=pet_names.get(pet_id, f"未知精灵#{pet_id}"),
                effect_id=effect_id,
                icon_asset_status=asset_check.status,
                icon_asset_error=asset_check.error,
                icon_png_error=png_render.error,
            )
        )
    return issues


def _effect_icon_ids(config_data: ConfigPackageData) -> list[int]:
    return sorted({item.icon_id for item in config_data.soulmark_icons})


def _seed_effect_icon_png_cache_from_database(db_path: Path) -> int:
    if not db_path.is_file():
        logger.info("No previous IronsBot database to seed effect icon PNG cache")
        return 0
    try:
        with sqlite3.connect(db_path) as conn:
            metadata_row = conn.execute(
                """
                SELECT value
                FROM ironsbot_metadata
                WHERE key = 'effect_icon_png_cache_version'
                """
            ).fetchone()
            if metadata_row is None or metadata_row[0] != EFFECT_ICON_PNG_CACHE_VERSION:
                logger.info(
                    "Previous effect icon PNG cache uses a different renderer version; "
                    "not seeding it"
                )
                return 0
            rows = conn.execute(
                f"""
                SELECT
                    icon_id,
                    icon_png,
                    icon_asset_content_length,
                    icon_asset_content_type
                FROM {SOULMARK_ICON_TABLE}
                WHERE icon_png_available = 1
                  AND icon_png IS NOT NULL
                  AND icon_asset_content_length IS NOT NULL
                GROUP BY icon_id
                """
            ).fetchall()
    except sqlite3.Error as error:
        logger.warning(
            "Unable to seed effect icon PNG cache from %s: %s",
            db_path,
            _short_error(error),
        )
        return 0

    seeded_count = 0
    for icon_id, png_data, content_length, content_type in rows:
        if not isinstance(png_data, bytes):
            continue
        check = EffectIconAssetCheck(
            icon_id=int(icon_id),
            url=_effect_icon_asset_url(int(icon_id)),
            available=True,
            status=200,
            content_type=str(content_type),
            content_length=int(content_length),
            error="",
        )
        if _save_effect_icon_png_cache(int(icon_id), png_data, check):
            seeded_count += 1
    logger.info(
        "Seeded %s effect icon PNGs from previous IronsBot database",
        seeded_count,
    )
    return seeded_count


def _export_effect_icon_png_cache_shard(
    icon_ids: list[int],
    output_dir: Path,
) -> int:
    exported_count = 0
    target_dir = output_dir / EFFECT_ICON_PNG_CACHE_VERSION
    target_dir.mkdir(parents=True, exist_ok=True)
    for icon_id in icon_ids:
        source_path = _effect_icon_png_cache_path(icon_id)
        metadata_path = _effect_icon_png_cache_metadata_path(icon_id)
        if not source_path.is_file() or not metadata_path.is_file():
            continue
        shutil.copy2(source_path, target_dir / source_path.name)
        shutil.copy2(metadata_path, target_dir / metadata_path.name)
        exported_count += 1
    logger.info(
        "Exported %s effect icon PNG cache entries to %s",
        exported_count,
        output_dir,
    )
    return exported_count


def _render_effect_icon_png_cache_shard(
    *,
    shard_index: int,
    shard_count: int,
    output_dir: Path,
) -> tuple[int, int]:
    if shard_count <= 0:
        raise ValueError("Effect icon shard count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(
            f"Effect icon shard index must be in 0..{shard_count - 1}"
        )

    config_data = _fetch_config_package_data()
    icon_ids = set(_effect_icon_ids(config_data))
    fallback_icon_ids = _unity_effect_icon_swf_fallback_icon_ids(icon_ids)
    shard_icon_ids = fallback_icon_ids[shard_index::shard_count]
    logger.info(
        "Rendering SWF fallback effect icon cache shard %s/%s: %s icons",
        shard_index + 1,
        shard_count,
        len(shard_icon_ids),
    )
    checks = _verify_effect_icon_assets(set(shard_icon_ids), require_any=False)
    renders = _render_effect_icon_png_assets(checks, require_any=False)
    _export_effect_icon_png_cache_shard(shard_icon_ids, output_dir)
    return len(shard_icon_ids), sum(
        1 for render in renders.values() if render.available
    )


def _fetch_config_package_data() -> ConfigPackageData:
    base_url = CONFIG_PACKAGE_BASE_URL.rstrip("/") + "/"
    version, manifest = _fetch_package_manifest(base_url, PACKAGE_NAME)
    for bundle in manifest.bundles:
        if bundle.name == CONFIG_BUNDLE_NAME:
            break
    else:
        if len(manifest.bundles) != 1:
            raise ValueError("ConfigPackage bundle not found")
        bundle = manifest.bundles[0]
    bundle_url = urljoin(base_url, bundle.file_hash)
    bundle_data = _download_bytes(bundle_url)
    assets = _extract_text_assets(bundle_data, CONFIG_TEXT_ASSETS)
    return ConfigPackageData(
        version=version,
        bundle_url=bundle_url,
        mintmark_quality=_parse_mintmark_quality_bytes(assets[MINTMARK_BYTES_NAME]),
        skin_store_prices=_parse_skin_store_pool(assets[SKIN_STORE_POOL_BYTES_NAME]),
        skin_shop_prices=_parse_skin_shop(assets[SKIN_SHOP_BYTES_NAME]),
        skin_item_tips=_parse_items_tip(assets[ITEMS_TIP_BYTES_NAME]),
        soulmark_icons=_parse_effect_icon(assets[EFFECT_ICON_BYTES_NAME]),
        autocard_season_effects=_parse_autocard_season_effects(
            assets[AUTOCARD_SEASON_EFFECT_BYTES_NAME]
        ),
    )


def _load_autocard_data() -> AutocardData:
    content_json, content_source = _load_autocard_json(AUTOCARD_CONTENT_FILE)
    nature_json, nature_source = _load_autocard_json(AUTOCARD_NATURE_FILE)
    role_json, role_source = _load_autocard_json(AUTOCARD_ROLE_FILE)
    buff_json, buff_source = _load_autocard_json(AUTOCARD_BUFF_FILE)
    source = "\n".join(
        sorted({buff_source, content_source, nature_source, role_source})
    )
    return AutocardData(
        cards=_json_data_rows(content_json),
        roles=_json_data_rows(role_json),
        natures=_json_data_rows(nature_json),
        buffs=_json_data_rows(buff_json),
        source=source,
    )


def _load_item_exchange_prices() -> list[ItemExchangePrice]:
    try:
        currency_names = _parse_unity_item_names(
            _download_bytes(UNITY_ITEM_CATALOG_URL)
        )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning("Official Unity item names skipped: %s", _short_error(error))
        currency_names = {}

    sources = (
        (BATTLEPASS_SHOP_SOURCE_NAME, BATTLEPASS_SHOP_URL, _parse_battlepass_shop),
        (ACTIVITY_SHOP_SOURCE_NAME, ACTIVITY_SHOP_URL, _parse_activity_shop),
        (
            SPECIAL_SKILL_SHOP_SOURCE_NAME,
            SPECIAL_SKILL_SHOP_URL,
            _parse_special_skill_shop,
        ),
    )
    prices: list[ItemExchangePrice] = []
    for source_name, source_url, parser in sources:
        try:
            prices.extend(
                replace(
                    price,
                    currency_name=currency_names.get(price.currency_item_id, ""),
                )
                for price in parser(_download_bytes(source_url))
            )
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            logger.warning(
                "Item exchange price source skipped (%s): %s",
                source_name,
                _short_error(error),
            )
    return prices


def _load_effect_descriptions() -> list[EffectDescription]:
    try:
        return _parse_effect_descriptions(_download_bytes(EFFECT_DESCRIPTION_URL))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning(
            "Effect description source skipped: %s",
            _short_error(error),
        )
        return []


def _load_special_effect_statuses() -> list[SpecialEffectStatus]:
    try:
        return _parse_special_effect_statuses(
            _download_bytes(SPECIAL_EFFECT_STATUS_URL)
        )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        logger.warning(
            "Special effect status source skipped: %s",
            _short_error(error),
        )
        return []


def _load_autocard_json(filename: str) -> tuple[dict[str, object], str]:
    if AUTOCARD_JSON_DIR:
        path = Path(AUTOCARD_JSON_DIR) / filename
        if path.exists():
            return (
                json.loads(path.read_text(encoding="utf-8")),
                str(path),
            )

    base_url = AUTOCARD_JSON_BASE_URL.rstrip("/") + "/"
    url = urljoin(base_url, filename)
    return (
        json.loads(_download_bytes(url).decode("utf-8-sig")),
        url,
    )


def _json_data_rows(raw: dict[str, object]) -> list[dict[str, object]]:
    rows = raw.get("data", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _item_int(item: dict[str, object], *names: str) -> int:
    for name in names:
        if name not in item:
            continue
        try:
            return int(item.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def _item_text(item: dict[str, object], *names: str) -> str:
    for name in names:
        value = item.get(name)
        if value is not None:
            return str(value)
    return ""


def _parse_unity_item_names(data: bytes) -> dict[int, str]:
    """Read exchange-currency labels from the official Unity item catalog."""

    raw = json.loads(data.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Unity item catalog root must be an object")
    items_root = raw.get("root")
    if not isinstance(items_root, dict):
        raise ValueError("Unity item catalog has no root object")
    rows = items_root.get("items")
    if not isinstance(rows, list):
        raise ValueError("Unity item catalog has no items list")

    item_names: dict[int, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item_id = _item_int(row, "id")
        item_name = _item_text(row, "name").strip()
        if item_id <= 0 or not item_name:
            continue
        existing_name = item_names.setdefault(item_id, item_name)
        if existing_name != item_name:
            raise ValueError(
                f"Unity item catalog has conflicting name for item {item_id} "
                f"at index {index}"
            )
    return item_names


def _partner_contract_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Invalid contract {label}: {value!r}")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid contract {label}: {value!r}") from error


def _parse_pet_partner_data(partner_contracts_data: bytes) -> PetPartnerData:
    """Parse canonical contract data extracted from the official ConfigPackage."""

    raw = json.loads(partner_contracts_data.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Partner contracts root must be an object")
    if raw.get("schema_version") != PARTNER_CONTRACTS_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported partner contracts schema: "
            f"{raw.get('schema_version')!r}"
        )
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("package") != "ConfigPackage"
        or not isinstance(source.get("config_package_version"), str)
        or not source["config_package_version"].strip()
    ):
        raise ValueError("Partner contracts are not sourced from ConfigPackage")

    group_rows = raw.get("groups")
    if not isinstance(group_rows, list):
        raise ValueError("Partner contracts groups must be a list")

    groups: list[PetPartnerGroup] = []
    member_pet_ids: set[int] = set()
    seen_group_ids: set[int] = set()
    for index, row in enumerate(group_rows):
        if not isinstance(row, dict):
            raise ValueError(f"Partner contract group {index} must be an object")
        group_id = _partner_contract_int(row.get("key"), f"groups[{index}].key")
        group_type = _item_text(row, "type").strip()
        name = _item_text(row, "name").strip()
        cost = _partner_contract_int(row.get("cost"), f"groups[{index}].cost")
        raw_members = row.get("member_pet_ids")
        if not isinstance(raw_members, list):
            raise ValueError(f"Partner contract group {group_id} has invalid members")
        members = tuple(
            _partner_contract_int(
                member_id,
                f"groups[{index}].member_pet_ids[{member_index}]",
            )
            for member_index, member_id in enumerate(raw_members)
        )
        if (
            group_id <= 0
            or not group_type
            or not name
            or cost <= 0
            or len(members) < 2
            or group_id in seen_group_ids
            or any(member_id <= 0 for member_id in members)
            or len(set(members)) != len(members)
            or any(member_id in member_pet_ids for member_id in members)
        ):
            raise ValueError(f"Invalid partner contract group {group_id}")
        if group_type != PARTNER_CONTRACT_GROUP_TYPE:
            continue
        seen_group_ids.add(group_id)
        member_pet_ids.update(members)
        groups.append(
            PetPartnerGroup(
                group_id=group_id,
                name=name,
                member_pet_ids=members,
                cost_item_id=CONTRACT_BADGE_ITEM_ID,
                cost_item_name=CONTRACT_BADGE_ITEM_NAME,
                cost_item_quantity=cost,
            )
        )

    upgrade_rows = raw.get("upgrades")
    if not isinstance(upgrade_rows, list):
        raise ValueError("Partner contract upgrades must be a list")

    upgrades: dict[int, PetPartnerUpgrade] = {}
    for index, row in enumerate(upgrade_rows):
        if not isinstance(row, dict):
            raise ValueError(f"Partner contract upgrade {index} must be an object")
        pet_id = _partner_contract_int(row.get("pet_id"), f"upgrades[{index}].pet_id")
        if pet_id <= 0 or pet_id not in member_pet_ids or pet_id in upgrades:
            continue
        raw_skill_ids = row.get("skill_ids", [])
        if not isinstance(raw_skill_ids, list):
            raise ValueError(f"Partner contract upgrade {pet_id} has invalid skill IDs")
        skill_ids = [
            _partner_contract_int(
                skill_id,
                f"upgrades[{index}].skill_ids[{skill_index}]",
            )
            for skill_index, skill_id in enumerate(raw_skill_ids)
        ]
        skill_id = next((value for value in skill_ids if value > 0), None)
        source_before_description = _item_text(row, "before_description").strip()
        source_after_description = _item_text(row, "after_description").strip()
        if PARTNER_CONTRACTS_V1_DESCRIPTIONS_REVERSED:
            source_before_description, source_after_description = (
                source_after_description,
                source_before_description,
            )

        upgrades[pet_id] = PetPartnerUpgrade(
            pet_id=pet_id,
            before_description=source_before_description,
            after_description=source_after_description,
            skill_id=skill_id,
        )

    return PetPartnerData(
        groups=sorted(groups, key=lambda group: group.group_id),
        upgrades=[upgrades[pet_id] for pet_id in sorted(upgrades)],
    )


def _load_pet_partner_data() -> PetPartnerData:
    try:
        return _parse_pet_partner_data(_download_bytes(PARTNER_CONTRACTS_URL))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        raise RuntimeError(
            "Unable to load official ConfigPackage partner contracts: "
            f"{_short_error(error)}"
        ) from error


def _dump_json(item: dict[str, object]) -> str:
    return json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def _quick_check(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        raise sqlite3.DatabaseError(
            f"SQLite quick_check failed: {result}"
        )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    }


def _replace_autocard_role_table(
    conn: sqlite3.Connection,
    data: AutocardData,
    updated_at: float,
) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS autocard_element_type (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_ROLE_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            health INTEGER NOT NULL,
            skill_desc TEXT NOT NULL,
            is_passive_skill BOOLEAN NOT NULL,
            skill_cost INTEGER,
            skill_game_limit INTEGER,
            skill_round_limit INTEGER,
            element_type_id INTEGER NOT NULL,
            FOREIGN KEY (element_type_id) REFERENCES autocard_element_type(id)
        )
        """
    )
    columns = _table_columns(conn, AUTOCARD_ROLE_TABLE)
    official_columns = {
        "id",
        "name",
        "description",
        "health",
        "skill_desc",
        "is_passive_skill",
        "skill_cost",
        "skill_game_limit",
        "skill_round_limit",
        "element_type_id",
    }
    if columns != official_columns:
        raise RuntimeError(
            "Unsupported autocard_role schema; expected official columns, got: "
            + ", ".join(sorted(columns))
        )

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_ROLE_RAW_TABLE} (
            role_id INTEGER PRIMARY KEY,
            pic_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            skill_upgrade TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY (role_id) REFERENCES {AUTOCARD_ROLE_TABLE}(id)
        )
        """
    )
    raw_columns = _table_columns(conn, AUTOCARD_ROLE_RAW_TABLE)
    expected_raw_columns = {
        "role_id",
        "pic_id",
        "skill_id",
        "skill_name",
        "skill_upgrade",
        "raw_json",
        "source",
        "updated_at",
    }
    if raw_columns != expected_raw_columns:
        raise RuntimeError(
            "Unsupported autocard_role_raw schema; expected sidecar columns, got: "
            + ", ".join(sorted(raw_columns))
        )

    element_type_rows = [
        (_item_int(item, "id"), _item_text(item, "name"))
        for item in data.natures
        if _item_int(item, "id") > 0
    ]
    role_items = [
        item
        for item in data.roles
        if 0 < _item_int(item, "id") < 10000
    ]
    official_role_rows: list[tuple[object, ...]] = []
    raw_role_rows: list[tuple[object, ...]] = []
    for item in role_items:
        id_ = _item_int(item, "id")
        nature = _item_int(item, "nature")
        element_type_id = nature or 999
        is_passive_skill = not bool(
            _item_int(item, "skillType", "skill_type")
        )
        skill_cost = None
        skill_game_limit = None
        skill_round_limit = None
        if not is_passive_skill:
            skill_cost = _item_int(item, "skillCostNum", "skill_cost_num")
            skill_game_limit = _item_int(
                item, "skillGameLimit", "skill_game_limit"
            )
            skill_round_limit = _item_int(
                item, "skillRoundLimit", "skill_round_limit"
            )
        official_role_rows.append(
            (
                id_,
                _item_text(item, "name"),
                _item_text(item, "desc"),
                _item_int(item, "health"),
                _item_text(item, "skillTxt", "skill_txt"),
                int(is_passive_skill),
                skill_cost,
                skill_game_limit,
                skill_round_limit,
                element_type_id,
            )
        )
        raw_role_rows.append(
            (
                id_,
                _item_int(item, "picID", "pic_id"),
                _item_int(item, "skillID", "skill_id"),
                _item_text(item, "skillName", "skill_name"),
                _item_text(item, "skillUpgrade", "skill_upgrade"),
                _dump_json(item),
                data.source,
                updated_at,
            )
        )

    conn.execute(f"DELETE FROM {AUTOCARD_ROLE_RAW_TABLE}")
    conn.execute(f"DELETE FROM {AUTOCARD_ROLE_TABLE}")
    if element_type_rows:
        placeholders = ", ".join("?" for _ in element_type_rows)
        conn.execute(
            f"DELETE FROM autocard_element_type WHERE id NOT IN ({placeholders})",
            tuple(id_ for id_, _ in element_type_rows),
        )
    conn.executemany(
        """
        INSERT INTO autocard_element_type (id, name)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET name = excluded.name
        """,
        element_type_rows,
    )
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_ROLE_TABLE} (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        official_role_rows,
    )
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_ROLE_RAW_TABLE} (
            role_id,
            pic_id,
            skill_id,
            skill_name,
            skill_upgrade,
            raw_json,
            source,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        raw_role_rows,
    )

    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{AUTOCARD_ROLE_TABLE}_name
        ON {AUTOCARD_ROLE_TABLE} (name)
        """
    )


def _replace_autocard_tables(
    conn: sqlite3.Connection,
    data: AutocardData,
    updated_at: float,
) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_CARD_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type INTEGER NOT NULL,
            nature INTEGER NOT NULL,
            attack INTEGER NOT NULL,
            health INTEGER NOT NULL,
            level INTEGER NOT NULL,
            cost INTEGER NOT NULL,
            compose INTEGER NOT NULL,
            card_text TEXT NOT NULL,
            description TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_CARD_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_CARD_TABLE}
            (
                id,
                name,
                type,
                nature,
                attack,
                health,
                level,
                cost,
                compose,
                card_text,
                description,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "name"),
                _item_int(item, "type"),
                _item_int(item, "nature"),
                _item_int(item, "attack"),
                _item_int(item, "health"),
                _item_int(item, "level"),
                _item_int(item, "cost"),
                _item_int(item, "compose"),
                _item_text(item, "cardTxt", "card_txt"),
                _item_text(item, "des"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.cards
            if _item_int(item, "id") > 0
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{AUTOCARD_CARD_TABLE}_name
        ON {AUTOCARD_CARD_TABLE} (name)
        """
    )

    _replace_autocard_role_table(conn, data, updated_at)

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_NATURE_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_NATURE_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_NATURE_TABLE}
            (id, name, raw_json, source, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "name"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.natures
            if _item_int(item, "id") > 0
        ],
    )

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_BUFF_TABLE} (
            id INTEGER PRIMARY KEY,
            object TEXT NOT NULL,
            param TEXT NOT NULL,
            param_description TEXT NOT NULL,
            is_death_effect INTEGER NOT NULL,
            is_place_effect INTEGER NOT NULL,
            effect_icon TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_BUFF_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_BUFF_TABLE}
            (
                id,
                object,
                param,
                param_description,
                is_death_effect,
                is_place_effect,
                effect_icon,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "object"),
                _item_text(item, "param"),
                _item_text(item, "paramDes", "param_des"),
                _item_int(item, "IsDeathEffect", "is_death_effect"),
                _item_int(item, "IsPlaceEffect", "is_place_effect"),
                _item_text(item, "effectIcon", "effect_icon"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.buffs
            if _item_int(item, "id") > 0
        ],
    )


def _replace_autocard_season_effect_table(
    conn: sqlite3.Connection,
    effects: list[AutocardSeasonEffect],
    updated_at: float,
) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_SEASON_EFFECT_TABLE} (
            id INTEGER PRIMARY KEY,
            sanctuary_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            buff_id TEXT NOT NULL,
            buff_param TEXT NOT NULL,
            count_buff_id TEXT NOT NULL,
            count_type INTEGER NOT NULL,
            count_num INTEGER NOT NULL,
            unlock_round INTEGER NOT NULL,
            pic_id INTEGER NOT NULL,
            season_id INTEGER NOT NULL,
            stage INTEGER NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_SEASON_EFFECT_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_SEASON_EFFECT_TABLE}
            (
                id,
                sanctuary_id,
                name,
                description,
                buff_id,
                buff_param,
                count_buff_id,
                count_type,
                count_num,
                unlock_round,
                pic_id,
                season_id,
                stage,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.effect_id,
                item.sanctuary_id,
                item.name,
                item.description,
                item.buff_id,
                item.buff_param,
                item.count_buff_id,
                item.count_type,
                item.count_num,
                item.unlock_round,
                item.pic_id,
                item.season_id,
                item.stage,
                _dump_json(
                    {
                        "id": item.effect_id,
                        "sanctuary_id": item.sanctuary_id,
                        "name": item.name,
                        "description": item.description,
                        "buff_id": item.buff_id,
                        "buff_param": item.buff_param,
                        "count_buff_id": item.count_buff_id,
                        "count_type": item.count_type,
                        "count_num": item.count_num,
                        "unlock_round": item.unlock_round,
                        "pic_id": item.pic_id,
                        "season_id": item.season_id,
                        "stage": item.stage,
                    }
                ),
                "ConfigPackage/autocardSeasonEffect.bytes",
                updated_at,
            )
            for item in effects
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS
            idx_{AUTOCARD_SEASON_EFFECT_TABLE}_sanctuary
        ON {AUTOCARD_SEASON_EFFECT_TABLE}
            (sanctuary_id, unlock_round, id)
        """
    )


def _replace_pet_partner_tables(
    conn: sqlite3.Connection,
    data: PetPartnerData,
    updated_at: float,
) -> None:
    """Replace contract-partner tables derived from official game config."""

    conn.execute(f"DROP TABLE IF EXISTS {PET_PARTNER_UPGRADE_TABLE}")
    conn.execute(f"DROP TABLE IF EXISTS {PET_PARTNER_MEMBER_TABLE}")
    conn.execute(f"DROP TABLE IF EXISTS {PET_PARTNER_GROUP_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {PET_PARTNER_GROUP_TABLE} (
            group_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            cost_item_id INTEGER NOT NULL,
            cost_item_name TEXT NOT NULL,
            cost_item_quantity INTEGER NOT NULL,
            required_pet_count INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE {PET_PARTNER_MEMBER_TABLE} (
            group_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            display_order INTEGER NOT NULL,
            PRIMARY KEY (group_id, pet_id)
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE {PET_PARTNER_UPGRADE_TABLE} (
            pet_id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            before_description TEXT NOT NULL,
            after_description TEXT NOT NULL,
            skill_id INTEGER,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {PET_PARTNER_GROUP_TABLE}
            (
                group_id,
                name,
                cost_item_id,
                cost_item_name,
                cost_item_quantity,
                required_pet_count,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                group.group_id,
                group.name,
                group.cost_item_id,
                group.cost_item_name,
                group.cost_item_quantity,
                len(group.member_pet_ids),
                "ConfigPackage/partner.bytes",
                updated_at,
            )
            for group in data.groups
        ],
    )
    conn.executemany(
        f"""
        INSERT INTO {PET_PARTNER_MEMBER_TABLE}
            (group_id, pet_id, display_order)
        VALUES (?, ?, ?)
        """,
        [
            (group.group_id, pet_id, display_order)
            for group in data.groups
            for display_order, pet_id in enumerate(group.member_pet_ids, start=1)
        ],
    )
    group_id_by_pet = {
        pet_id: group.group_id
        for group in data.groups
        for pet_id in group.member_pet_ids
    }
    conn.executemany(
        f"""
        INSERT INTO {PET_PARTNER_UPGRADE_TABLE}
            (
                pet_id,
                group_id,
                before_description,
                after_description,
                skill_id,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                upgrade.pet_id,
                group_id_by_pet[upgrade.pet_id],
                upgrade.before_description,
                upgrade.after_description,
                upgrade.skill_id,
                PET_PARTNER_UPGRADE_NORMALIZED_SOURCE,
                updated_at,
            )
            for upgrade in data.upgrades
            if upgrade.pet_id in group_id_by_pet
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX idx_{PET_PARTNER_MEMBER_TABLE}_pet_id
        ON {PET_PARTNER_MEMBER_TABLE} (pet_id)
        """
    )
    conn.execute(
        f"""
        CREATE INDEX idx_{PET_PARTNER_UPGRADE_TABLE}_group_id
        ON {PET_PARTNER_UPGRADE_TABLE} (group_id)
        """
    )


def _merge_ironsbot_tables(
    db_path: Path,
    *,
    config_data: ConfigPackageData,
    autocard_data: AutocardData,
    item_exchange_prices: list[ItemExchangePrice],
    effect_descriptions: list[EffectDescription],
    special_effect_statuses: list[SpecialEffectStatus],
    pet_partner_data: PetPartnerData,
    weekly_preview_probe: dict[str, str],
    skin_image_resolutions: list[SkinImageResolution] | None = None,
) -> None:
    now = time.time()
    skin_image_resolutions = skin_image_resolutions or []
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MINTMARK_QUALITY_TABLE} (
                mintmark_id INTEGER PRIMARY KEY,
                quality INTEGER NOT NULL,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(f"DELETE FROM {MINTMARK_QUALITY_TABLE}")
        conn.executemany(
            f"""
            INSERT INTO {MINTMARK_QUALITY_TABLE}
                (mintmark_id, quality, source, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (mintmark_id, quality, "ConfigPackage/mintmark.bytes", now)
                for mintmark_id, quality in sorted(
                    config_data.mintmark_quality.items()
                )
            ],
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SKIN_STORE_PRICE_TABLE} (
                row_index INTEGER PRIMARY KEY,
                skin_id INTEGER NOT NULL,
                pool_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                original_price INTEGER NOT NULL,
                discount_rate INTEGER NOT NULL,
                selected_price INTEGER NOT NULL,
                ticket_id INTEGER NOT NULL,
                ticket_num INTEGER NOT NULL,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(f"DELETE FROM {SKIN_STORE_PRICE_TABLE}")
        conn.executemany(
            f"""
            INSERT INTO {SKIN_STORE_PRICE_TABLE}
                (
                    row_index,
                    skin_id,
                    pool_id,
                    price,
                    original_price,
                    discount_rate,
                    selected_price,
                    ticket_id,
                    ticket_num,
                    start_time,
                    end_time,
                    source,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    index,
                    item.skin_id,
                    item.pool_id,
                    item.price,
                    item.original_price,
                    item.discount_rate,
                    item.selected_price,
                    item.ticket_id,
                    item.ticket_num,
                    item.start_time,
                    item.end_time,
                    "ConfigPackage/skinStorePool.bytes",
                    now,
                )
                for index, item in enumerate(config_data.skin_store_prices, start=1)
            ],
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SKIN_STORE_PRICE_TABLE}_skin_id
            ON {SKIN_STORE_PRICE_TABLE} (skin_id)
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SKIN_SHOP_PRICE_TABLE} (
                skin_id INTEGER PRIMARY KEY,
                resource_id INTEGER NOT NULL,
                card_price INTEGER NOT NULL,
                diamond_price INTEGER NOT NULL,
                original_price INTEGER NOT NULL,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(f"DELETE FROM {SKIN_SHOP_PRICE_TABLE}")
        conn.executemany(
            f"""
            INSERT INTO {SKIN_SHOP_PRICE_TABLE}
                (
                    skin_id,
                    resource_id,
                    card_price,
                    diamond_price,
                    original_price,
                    source,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.skin_id,
                    item.resource_id,
                    item.card_price,
                    item.diamond_price,
                    item.original_price,
                    "ConfigPackage/skin_shop.bytes",
                    now,
                )
                for item in config_data.skin_shop_prices
            ],
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SKIN_ITEM_TIP_TABLE} (
                item_id INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(f"DELETE FROM {SKIN_ITEM_TIP_TABLE}")
        conn.executemany(
            f"""
            INSERT INTO {SKIN_ITEM_TIP_TABLE}
                (item_id, description, source, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (item_id, description, "ConfigPackage/itemsTip.bytes", now)
                for item_id, description in sorted(
                    config_data.skin_item_tips.items()
                )
            ],
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SKIN_IMAGE_RESOLUTION_TABLE} (
                skin_id INTEGER PRIMARY KEY,
                head_resource_id INTEGER NOT NULL,
                body_resource_id INTEGER NOT NULL,
                head_resolution TEXT NOT NULL,
                body_resolution TEXT NOT NULL,
                source_pet_id INTEGER,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(f"DELETE FROM {SKIN_IMAGE_RESOLUTION_TABLE}")
        conn.executemany(
            f"""
            INSERT INTO {SKIN_IMAGE_RESOLUTION_TABLE}
                (
                    skin_id,
                    head_resource_id,
                    body_resource_id,
                    head_resolution,
                    body_resolution,
                    source_pet_id,
                    source,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    resolution.skin_id,
                    resolution.head_resource_id,
                    resolution.body_resource_id,
                    resolution.head_resolution,
                    resolution.body_resolution,
                    resolution.source_pet_id,
                    "official pet image assets",
                    now,
                )
                for resolution in skin_image_resolutions
            ],
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SKIN_IMAGE_RESOLUTION_TABLE}_source_pet_id
            ON {SKIN_IMAGE_RESOLUTION_TABLE} (source_pet_id)
            """
        )
        conn.execute(f"DROP TABLE IF EXISTS {ITEM_EXCHANGE_PRICE_TABLE}")
        conn.execute(
            f"""
            CREATE TABLE {ITEM_EXCHANGE_PRICE_TABLE} (
                source_key TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_entry_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_quantity INTEGER NOT NULL,
                currency_item_id INTEGER NOT NULL,
                currency_name TEXT NOT NULL,
                amount INTEGER NOT NULL,
                purchase_limit INTEGER,
                start_time INTEGER NOT NULL,
                end_time INTEGER NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (source_key, source_entry_id)
            )
            """
        )
        conn.executemany(
            f"""
            INSERT INTO {ITEM_EXCHANGE_PRICE_TABLE}
                (
                    source_key,
                    source_name,
                    source_entry_id,
                    item_id,
                    item_name,
                    item_quantity,
                    currency_item_id,
                    currency_name,
                    amount,
                    purchase_limit,
                    start_time,
                    end_time,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item.source_key,
                    item.source_name,
                    item.source_entry_id,
                    item.item_id,
                    item.item_name,
                    item.item_quantity,
                    item.currency_item_id,
                    item.currency_name,
                    item.amount,
                    item.purchase_limit,
                    item.start_time,
                    item.end_time,
                    now,
                )
                for item in item_exchange_prices
            ],
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{ITEM_EXCHANGE_PRICE_TABLE}_item_id
            ON {ITEM_EXCHANGE_PRICE_TABLE} (item_id)
            """
        )
        conn.execute(f"DROP TABLE IF EXISTS {EFFECT_DESCRIPTION_TABLE}")
        conn.execute(
            f"""
            CREATE TABLE {EFFECT_DESCRIPTION_TABLE} (
                effect_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.executemany(
            f"""
            INSERT INTO {EFFECT_DESCRIPTION_TABLE}
                (effect_id, name, description, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    effect.effect_id,
                    effect.name,
                    effect.description,
                    now,
                )
                for effect in effect_descriptions
            ],
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{EFFECT_DESCRIPTION_TABLE}_name
            ON {EFFECT_DESCRIPTION_TABLE} (name)
            """
        )
        conn.execute(f"DROP TABLE IF EXISTS {SPECIAL_EFFECT_STATUS_TABLE}")
        conn.execute(
            f"""
            CREATE TABLE {SPECIAL_EFFECT_STATUS_TABLE} (
                status_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                show_monster_id INTEGER NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (status_id, name)
            )
            """
        )
        conn.executemany(
            f"""
            INSERT INTO {SPECIAL_EFFECT_STATUS_TABLE}
                (status_id, name, description, show_monster_id, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    status.status_id,
                    status.name,
                    status.description,
                    status.show_monster_id,
                    now,
                )
                for status in special_effect_statuses
            ],
        )
        conn.execute(
            f"""
            CREATE INDEX idx_{SPECIAL_EFFECT_STATUS_TABLE}_name
            ON {SPECIAL_EFFECT_STATUS_TABLE} (name)
            """
        )
        deduplicated_soulmark_icons = sorted(
            {
                (
                    item.soulmark_id,
                    item.pet_id,
                    item.effect_id,
                    item.icon_id,
                )
                for item in config_data.soulmark_icons
            }
        )
        effect_icon_resolution = _resolve_effect_icon_png_assets(
            {icon_id for _, _, _, icon_id in deduplicated_soulmark_icons}
        )
        effect_icon_asset_checks = effect_icon_resolution.asset_checks
        effect_icon_png_renders = effect_icon_resolution.png_renders
        issue_pet_ids = sorted(
            {
                pet_id
                for _, pet_id, _, icon_id in deduplicated_soulmark_icons
                if not effect_icon_png_renders[icon_id].available
            }
        )
        pet_names: dict[int, str] = {}
        if issue_pet_ids:
            placeholders = ", ".join("?" for _ in issue_pet_ids)
            pet_names = {
                int(pet_id): str(name)
                for pet_id, name in conn.execute(
                    f"SELECT id, name FROM pet WHERE id IN ({placeholders})",
                    issue_pet_ids,
                )
            }
        soulmark_icon_render_issues = _collect_soulmark_icon_render_issues(
            deduplicated_soulmark_icons,
            effect_icon_asset_checks,
            effect_icon_png_renders,
            pet_names,
        )
        soulmark_icon_rows = []
        for soulmark_id, pet_id, effect_id, icon_id in deduplicated_soulmark_icons:
            asset_check = effect_icon_asset_checks[icon_id]
            png_render = effect_icon_png_renders[icon_id]
            soulmark_icon_rows.append(
                (
                    soulmark_id,
                    pet_id,
                    effect_id,
                    icon_id,
                    _effect_icon_runtime_asset_url(asset_check),
                    int(asset_check.available),
                    asset_check.status,
                    asset_check.content_type,
                    asset_check.content_length,
                    asset_check.error,
                    png_render.data,
                    int(png_render.available),
                    png_render.content_type,
                    png_render.content_length,
                    png_render.error,
                    "ConfigPackage/effectIcon.bytes",
                    now,
                )
            )
        conn.execute(f"DROP TABLE IF EXISTS {SOULMARK_ICON_TABLE}")
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SOULMARK_ICON_TABLE} (
                soulmark_id INTEGER NOT NULL,
                pet_id INTEGER NOT NULL,
                effect_id INTEGER NOT NULL,
                icon_id INTEGER NOT NULL,
                icon_asset_url TEXT,
                icon_asset_available INTEGER NOT NULL,
                icon_asset_status INTEGER NOT NULL,
                icon_asset_content_type TEXT NOT NULL,
                icon_asset_content_length INTEGER,
                icon_asset_error TEXT NOT NULL,
                icon_png BLOB,
                icon_png_available INTEGER NOT NULL,
                icon_png_content_type TEXT NOT NULL,
                icon_png_content_length INTEGER,
                icon_png_error TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (soulmark_id, pet_id, effect_id, icon_id)
            )
            """
        )
        conn.executemany(
            f"""
            INSERT INTO {SOULMARK_ICON_TABLE}
                (
                    soulmark_id,
                    pet_id,
                    effect_id,
                    icon_id,
                    icon_asset_url,
                    icon_asset_available,
                    icon_asset_status,
                    icon_asset_content_type,
                    icon_asset_content_length,
                    icon_asset_error,
                    icon_png,
                    icon_png_available,
                    icon_png_content_type,
                    icon_png_content_length,
                    icon_png_error,
                    source,
                    updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            soulmark_icon_rows,
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SOULMARK_ICON_TABLE}_soulmark_id
            ON {SOULMARK_ICON_TABLE} (soulmark_id)
            """
        )
        conn.execute(f"DROP TABLE IF EXISTS {SOULMARK_ICON_RENDER_ISSUE_TABLE}")
        conn.execute(
            f"""
            CREATE TABLE {SOULMARK_ICON_RENDER_ISSUE_TABLE} (
                icon_id INTEGER NOT NULL,
                soulmark_id INTEGER NOT NULL,
                pet_id INTEGER NOT NULL,
                pet_name TEXT NOT NULL,
                effect_id INTEGER NOT NULL,
                icon_asset_status INTEGER NOT NULL,
                icon_asset_error TEXT NOT NULL,
                icon_png_error TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (icon_id, soulmark_id, pet_id, effect_id)
            )
            """
        )
        conn.executemany(
            f"""
            INSERT INTO {SOULMARK_ICON_RENDER_ISSUE_TABLE}
                (
                    icon_id,
                    soulmark_id,
                    pet_id,
                    pet_name,
                    effect_id,
                    icon_asset_status,
                    icon_asset_error,
                    icon_png_error,
                    updated_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    issue.icon_id,
                    issue.soulmark_id,
                    issue.pet_id,
                    issue.pet_name,
                    issue.effect_id,
                    issue.icon_asset_status,
                    issue.icon_asset_error,
                    issue.icon_png_error,
                    now,
                )
                for issue in soulmark_icon_render_issues
            ],
        )
        conn.execute(
            f"""
            CREATE INDEX idx_{SOULMARK_ICON_RENDER_ISSUE_TABLE}_pet_id
            ON {SOULMARK_ICON_RENDER_ISSUE_TABLE} (pet_id)
            """
        )
        _replace_autocard_tables(conn, autocard_data, now)
        _replace_autocard_season_effect_table(
            conn,
            config_data.autocard_season_effects,
            now,
        )
        _replace_pet_partner_tables(conn, pet_partner_data, now)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ironsbot_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        metadata = {
            "built_at": str(int(now)),
            "upstream_seerapi_url": UPSTREAM_SEERAPI_URL,
            "config_package_base_url": CONFIG_PACKAGE_BASE_URL,
            "config_package_version": config_data.version,
            "config_bundle_url": config_data.bundle_url,
            "effect_icon_asset_base_url": EFFECT_ICON_ASSET_BASE_URL,
            "effect_icon_asset_suffix": EFFECT_ICON_ASSET_SUFFIX,
            "effect_icon_unity_png_enabled": str(int(UNITY_EFFECT_ICON_PNG_ENABLED)),
            "effect_icon_unity_package_base_url": DEFAULT_PACKAGE_BASE_URL,
            "effect_icon_unity_package_version": (
                effect_icon_resolution.unity_package_version
            ),
            "effect_icon_unity_manifest_icon_count": str(
                effect_icon_resolution.unity_manifest_icon_count
            ),
            "effect_icon_unity_png_available_count": str(
                effect_icon_resolution.unity_png_available_count
            ),
            "effect_icon_unity_png_missing_count": str(
                len(effect_icon_resolution.unity_missing_icon_ids)
            ),
            "effect_icon_swf_fallback_icon_count": str(
                effect_icon_resolution.swf_fallback_icon_count
            ),
            "effect_icon_swf_fallback_icon_ids": ",".join(
                str(icon_id) for icon_id in effect_icon_resolution.unity_missing_icon_ids
            ),
            "effect_icon_asset_checked_count": str(len(effect_icon_asset_checks)),
            "effect_icon_asset_available_count": str(
                sum(1 for check in effect_icon_asset_checks.values() if check.available)
            ),
            "effect_icon_asset_missing_count": str(
                sum(
                    1
                    for check in effect_icon_asset_checks.values()
                    if not check.available
                )
            ),
            "effect_icon_png_render_enabled": str(
                int(EFFECT_ICON_PNG_RENDER_ENABLED)
            ),
            "effect_icon_png_renderer": (
                "unity-defaultpackage-png+ffdec-swf-fallback"
            ),
            "effect_icon_png_render_java_command": (
                EFFECT_ICON_PNG_RENDER_JAVA_COMMAND
            ),
            "effect_icon_png_render_ffdec_jar": str(
                EFFECT_ICON_PNG_RENDER_FFDEC_JAR
            ),
            "effect_icon_png_cache_version": EFFECT_ICON_PNG_CACHE_VERSION,
            "effect_icon_png_render_zoom": str(EFFECT_ICON_PNG_RENDER_ZOOM),
            "effect_icon_png_render_checked_count": str(
                len(effect_icon_png_renders)
            ),
            "effect_icon_png_render_available_count": str(
                sum(
                    1
                    for render in effect_icon_png_renders.values()
                    if render.available
                )
            ),
            "effect_icon_png_render_missing_count": str(
                sum(
                    1
                    for render in effect_icon_png_renders.values()
                    if not render.available
                )
            ),
            "effect_icon_png_render_issue_row_count": str(
                len(soulmark_icon_render_issues)
            ),
            "mintmark_quality_count": str(len(config_data.mintmark_quality)),
            "skin_store_price_count": str(len(config_data.skin_store_prices)),
            "skin_shop_price_count": str(len(config_data.skin_shop_prices)),
            "skin_item_tip_count": str(len(config_data.skin_item_tips)),
            "skin_image_resolution_count": str(len(skin_image_resolutions)),
            "skin_image_resolution_fallback_count": str(
                sum(
                    1
                    for resolution in skin_image_resolutions
                    if resolution.head_resolution != "direct_skin"
                    or resolution.body_resolution != "direct_skin"
                )
            ),
            "skin_image_resolution_unresolved_count": str(
                sum(
                    1
                    for resolution in skin_image_resolutions
                    if resolution.head_resolution in {"unresolved", "unverified"}
                    or resolution.body_resolution in {"unresolved", "unverified"}
                )
            ),
            "item_exchange_price_count": str(len(item_exchange_prices)),
            "item_exchange_price_source_urls": "\n".join(
                (
                    BATTLEPASS_SHOP_URL,
                    ACTIVITY_SHOP_URL,
                    SPECIAL_SKILL_SHOP_URL,
                    UNITY_ITEM_CATALOG_URL,
                )
            ),
            "effect_description_count": str(len(effect_descriptions)),
            "effect_description_source_url": EFFECT_DESCRIPTION_URL,
            "special_effect_status_count": str(len(special_effect_statuses)),
            "special_effect_status_source_url": SPECIAL_EFFECT_STATUS_URL,
            "pet_partner_group_count": str(len(pet_partner_data.groups)),
            "pet_partner_upgrade_count": str(len(pet_partner_data.upgrades)),
            "pet_partner_source_url": PARTNER_CONTRACTS_URL,
            "soulmark_icon_count": str(len(soulmark_icon_rows)),
            "autocard_card_count": str(len(autocard_data.cards)),
            "autocard_role_count": str(len(autocard_data.roles)),
            "autocard_nature_count": str(len(autocard_data.natures)),
            "autocard_buff_count": str(len(autocard_data.buffs)),
            "autocard_season_effect_count": str(
                len(config_data.autocard_season_effects)
            ),
            "autocard_source": autocard_data.source,
            "weekly_preview_image_url": WEEKLY_PREVIEW_IMAGE_URL,
            "weekly_preview_source_url": WEEKLY_PREVIEW_SOURCE_URL,
            **weekly_preview_probe,
        }
        conn.executemany(
            """
            INSERT INTO ironsbot_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            sorted(metadata.items()),
        )
        conn.commit()


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-effect-icon-cache",
        type=Path,
        metavar="DATABASE",
        help="restore matching effect icon PNGs from a previous IronsBot SQLite database",
    )
    parser.add_argument(
        "--render-effect-icon-shard",
        type=int,
        metavar="INDEX",
        help="render one zero-based effect icon cache shard instead of building SQLite",
    )
    parser.add_argument(
        "--effect-icon-shard-count",
        type=int,
        default=1,
        metavar="COUNT",
        help="total shard count used with --render-effect-icon-shard",
    )
    parser.add_argument(
        "--export-effect-icon-cache-shard",
        type=Path,
        metavar="DIRECTORY",
        help="output directory for the rendered shard cache",
    )
    arguments = parser.parse_args()
    if arguments.render_effect_icon_shard is None:
        if (
            arguments.effect_icon_shard_count != 1
            or arguments.export_effect_icon_cache_shard is not None
        ):
            parser.error(
                "--effect-icon-shard-count and --export-effect-icon-cache-shard "
                "require --render-effect-icon-shard"
            )
    elif arguments.export_effect_icon_cache_shard is None:
        parser.error(
            "--render-effect-icon-shard requires --export-effect-icon-cache-shard"
        )
    return arguments


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _parse_cli_args()
    if arguments.seed_effect_icon_cache is not None:
        _seed_effect_icon_png_cache_from_database(arguments.seed_effect_icon_cache)
        return
    if arguments.render_effect_icon_shard is not None:
        icon_count, available_count = _render_effect_icon_png_cache_shard(
            shard_index=arguments.render_effect_icon_shard,
            shard_count=arguments.effect_icon_shard_count,
            output_dir=arguments.export_effect_icon_cache_shard,
        )
        logger.info(
            "Rendered effect icon cache shard: %s icons, %s available",
            icon_count,
            available_count,
        )
        return
    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if UPSTREAM_SEERAPI_PATH:
        logger.info(
            "Using verified upstream SeerAPI database: %s",
            UPSTREAM_SEERAPI_PATH,
        )
    else:
        logger.info("Downloading upstream SeerAPI database: %s", UPSTREAM_SEERAPI_URL)
    _copy_or_download_upstream_database(OUTPUT_DB)
    _quick_check(OUTPUT_DB)

    logger.info("Loading official ConfigPackage: %s", CONFIG_PACKAGE_BASE_URL)
    config_data = _fetch_config_package_data()
    if not config_data.mintmark_quality:
        raise ValueError("mintmark Quality map is empty")
    logger.info(
        "Loading autocard JSON data: %s",
        AUTOCARD_JSON_DIR or AUTOCARD_JSON_BASE_URL,
    )
    autocard_data = _load_autocard_data()
    logger.info("Loading official item exchange prices")
    item_exchange_prices = _load_item_exchange_prices()
    logger.info("Loading official named effect descriptions")
    effect_descriptions = _load_effect_descriptions()
    logger.info("Loading official special effect statuses")
    special_effect_statuses = _load_special_effect_statuses()
    logger.info("Loading official contract-partner data")
    pet_partner_data = _load_pet_partner_data()
    logger.info("Resolving classic skin image resources")
    skin_image_resolutions = _build_classic_skin_image_resolutions(OUTPUT_DB)
    logger.info("Probing weekly preview image: %s", WEEKLY_PREVIEW_IMAGE_URL)
    weekly_preview_probe = _probe_weekly_preview_image()

    _merge_ironsbot_tables(
        OUTPUT_DB,
        config_data=config_data,
        autocard_data=autocard_data,
        item_exchange_prices=item_exchange_prices,
        effect_descriptions=effect_descriptions,
        special_effect_statuses=special_effect_statuses,
        pet_partner_data=pet_partner_data,
        weekly_preview_probe=weekly_preview_probe,
        skin_image_resolutions=skin_image_resolutions,
    )
    _quick_check(OUTPUT_DB)
    size_mb = OUTPUT_DB.stat().st_size / 1024 / 1024
    logger.info(
        (
            "Built %s (%.2f MB), mintmark_quality rows: %s, "
            "skin shop rows: %s, exchange price rows: %s, effect descriptions: %s, "
            "special effect statuses: %s, "
            "soulmark icons: %s, classic skin image rows: %s, "
            "contract partners: %s, autocard cards: %s"
        ),
        OUTPUT_DB,
        size_mb,
        len(config_data.mintmark_quality),
        len(config_data.skin_shop_prices),
        len(item_exchange_prices),
        len(effect_descriptions),
        len(special_effect_statuses),
        len(config_data.soulmark_icons),
        len(skin_image_resolutions),
        len(pet_partner_data.groups),
        len(autocard_data.cards),
    )


if __name__ == "__main__":
    main()
