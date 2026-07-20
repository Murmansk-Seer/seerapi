# SPDX-License-Identifier: MIT
"""Build the IronsBot full Seer SQLite database.

The runtime bot downloads this database as its main data source. The upstream
SeerAPI database is used only as build input here; custom IronsBot-only fields
are merged into the final SQLite file before it is published.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
import io
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DB = ROOT / os.environ.get("IRONSBOT_DATA_OUTPUT", "ironsbot-data.sqlite")
UPSTREAM_SEERAPI_URL = os.environ.get(
    "IRONSBOT_DATA_UPSTREAM_SEERAPI_URL",
    "https://github.com/Murmansk-Seer/api-data/releases/download/latest/seerapi-data.sqlite",
)
CONFIG_PACKAGE_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_CONFIG_PACKAGE_BASE_URL",
    "https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/",
)
PACKAGE_NAME = "ConfigPackage"
CONFIG_BUNDLE_NAME = "pgame_configs_bytes"
MINTMARK_BYTES_NAME = "mintmark.bytes"
SKIN_STORE_POOL_BYTES_NAME = "skinStorePool.bytes"
SKIN_SHOP_BYTES_NAME = "skin_shop.bytes"
ITEMS_TIP_BYTES_NAME = "itemsTip.bytes"
EFFECT_ICON_BYTES_NAME = "effectIcon.bytes"
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
CONFIG_TEXT_ASSETS = {
    MINTMARK_BYTES_NAME,
    SKIN_STORE_POOL_BYTES_NAME,
    SKIN_SHOP_BYTES_NAME,
    ITEMS_TIP_BYTES_NAME,
    EFFECT_ICON_BYTES_NAME,
}
MINTMARK_QUALITY_TABLE = "mintmark_quality"
SKIN_STORE_PRICE_TABLE = "skin_store_price"
SKIN_SHOP_PRICE_TABLE = "skin_shop_price"
SKIN_ITEM_TIP_TABLE = "skin_item_tip"
ITEM_EXCHANGE_PRICE_TABLE = "item_exchange_price"
EFFECT_DESCRIPTION_TABLE = "effect_description"
SOULMARK_ICON_TABLE = "soulmark_icon"
PET_PARTNER_GROUP_TABLE = "pet_partner_group"
PET_PARTNER_MEMBER_TABLE = "pet_partner_member"
PET_PARTNER_UPGRADE_TABLE = "pet_partner_upgrade"
AUTOCARD_CARD_TABLE = "autocard_card"
AUTOCARD_ROLE_TABLE = "autocard_role"
AUTOCARD_NATURE_TABLE = "autocard_nature"
AUTOCARD_JSON_DIR = os.environ.get("IRONSBOT_DATA_AUTOCARD_JSON_DIR", "")
AUTOCARD_JSON_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_AUTOCARD_JSON_BASE_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/seer-unity-config-parser/main/json/",
)
AUTOCARD_CONTENT_FILE = "autocardContent.json"
AUTOCARD_NATURE_FILE = "autocardNature.json"
AUTOCARD_ROLE_FILE = "autocardRole.json"
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
PARTNER_CONTRACTS_URL = os.environ.get(
    "IRONSBOT_DATA_PARTNER_CONTRACTS_URL",
    "https://raw.githubusercontent.com/Murmansk-Seer/"
    "config-sources/main/unity/partner_contracts.json",
)
PARTNER_CONTRACTS_SCHEMA_VERSION = 1
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
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BundleInfo:
    name: str
    file_hash: str
    file_size: int


@dataclass(frozen=True, slots=True)
class ConfigPackageData:
    version: str
    bundle_url: str
    mintmark_quality: dict[int, int]
    skin_store_prices: list["SkinStorePrice"]
    skin_shop_prices: list["SkinShopPrice"]
    skin_item_tips: dict[int, str]
    soulmark_icons: list["SoulmarkIcon"]


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
class SkinShopPrice:
    skin_id: int
    resource_id: int
    card_price: int
    diamond_price: int
    original_price: int


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
class AutocardData:
    cards: list[dict[str, object]]
    roles: list[dict[str, object]]
    natures: list[dict[str, object]]
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


def _find_config_bundle(manifest_data: bytes) -> BundleInfo:
    reader = BytesReader(manifest_data)
    reader.read_u32()
    reader.read_text()
    reader.read_bool()
    reader.read_bool()
    reader.read_bool()
    reader.read_i32()
    reader.read_text()
    reader.read_text()

    asset_count = reader.read_i32()
    for _ in range(asset_count):
        reader.read_text()
        reader.read_i32()
        depend_count = reader.read_u16()
        for _ in range(depend_count):
            reader.read_i32()

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

    for bundle in bundles:
        if bundle.name == CONFIG_BUNDLE_NAME:
            return bundle

    if len(bundles) == 1:
        return bundles[0]

    raise ValueError("ConfigPackage bundle not found")


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
    if available_count == 0:
        raise ValueError("No official effect icon assets could be verified")
    if missing_checks:
        logger.warning(
            "Effect icon asset validation missing %s/%s icons; first missing: %s",
            len(missing_checks),
            len(checks),
            ", ".join(str(check.icon_id) for check in missing_checks[:10]),
        )
    return checks


def _fetch_config_package_data() -> ConfigPackageData:
    base_url = CONFIG_PACKAGE_BASE_URL.rstrip("/") + "/"
    version_url = urljoin(base_url, f"PackageManifest_{PACKAGE_NAME}.version")
    version = _download_bytes(f"{version_url}?t={int(time.time())}").decode().strip()

    manifest_url = urljoin(base_url, f"PackageManifest_{PACKAGE_NAME}_{version}.bytes")
    manifest_data = _download_bytes(manifest_url)
    bundle = _find_config_bundle(manifest_data)
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
    )


def _load_autocard_data() -> AutocardData:
    content_json, content_source = _load_autocard_json(AUTOCARD_CONTENT_FILE)
    nature_json, nature_source = _load_autocard_json(AUTOCARD_NATURE_FILE)
    role_json, role_source = _load_autocard_json(AUTOCARD_ROLE_FILE)
    source = "\n".join(
        sorted({content_source, nature_source, role_source})
    )
    return AutocardData(
        cards=_json_data_rows(content_json),
        roles=_json_data_rows(role_json),
        natures=_json_data_rows(nature_json),
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
        upgrades[pet_id] = PetPartnerUpgrade(
            pet_id=pet_id,
            before_description=_item_text(row, "before_description").strip(),
            after_description=_item_text(row, "after_description").strip(),
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

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {AUTOCARD_ROLE_TABLE} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            nature INTEGER NOT NULL,
            health INTEGER NOT NULL,
            skill_name TEXT NOT NULL,
            skill_text TEXT NOT NULL,
            skill_upgrade TEXT NOT NULL,
            description TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.execute(f"DELETE FROM {AUTOCARD_ROLE_TABLE}")
    conn.executemany(
        f"""
        INSERT INTO {AUTOCARD_ROLE_TABLE}
            (
                id,
                name,
                nature,
                health,
                skill_name,
                skill_text,
                skill_upgrade,
                description,
                raw_json,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                _item_int(item, "id"),
                _item_text(item, "name"),
                _item_int(item, "nature"),
                _item_int(item, "health"),
                _item_text(item, "skillName", "skill_name"),
                _item_text(item, "skillTxt", "skill_txt"),
                _item_text(item, "skillUpgrade", "skill_upgrade"),
                _item_text(item, "desc"),
                _dump_json(item),
                data.source,
                updated_at,
            )
            for item in data.roles
            if _item_int(item, "id") > 0
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{AUTOCARD_ROLE_TABLE}_name
        ON {AUTOCARD_ROLE_TABLE} (name)
        """
    )

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
                "ConfigPackage/partnerEffectUpgrade.bytes",
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
    pet_partner_data: PetPartnerData,
    weekly_preview_probe: dict[str, str],
) -> None:
    now = time.time()
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
        effect_icon_asset_checks = _verify_effect_icon_assets(
            {icon_id for _, _, _, icon_id in deduplicated_soulmark_icons}
        )
        soulmark_icon_rows = []
        for soulmark_id, pet_id, effect_id, icon_id in deduplicated_soulmark_icons:
            asset_check = effect_icon_asset_checks[icon_id]
            soulmark_icon_rows.append(
                (
                    soulmark_id,
                    pet_id,
                    effect_id,
                    icon_id,
                    asset_check.url if asset_check.available else None,
                    int(asset_check.available),
                    asset_check.status,
                    asset_check.content_type,
                    asset_check.content_length,
                    asset_check.error,
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
                    source,
                    updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            soulmark_icon_rows,
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SOULMARK_ICON_TABLE}_soulmark_id
            ON {SOULMARK_ICON_TABLE} (soulmark_id)
            """
        )
        _replace_autocard_tables(conn, autocard_data, now)
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
            "mintmark_quality_count": str(len(config_data.mintmark_quality)),
            "skin_store_price_count": str(len(config_data.skin_store_prices)),
            "skin_shop_price_count": str(len(config_data.skin_shop_prices)),
            "skin_item_tip_count": str(len(config_data.skin_item_tips)),
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
            "pet_partner_group_count": str(len(pet_partner_data.groups)),
            "pet_partner_upgrade_count": str(len(pet_partner_data.upgrades)),
            "pet_partner_source_url": PARTNER_CONTRACTS_URL,
            "soulmark_icon_count": str(len(soulmark_icon_rows)),
            "autocard_card_count": str(len(autocard_data.cards)),
            "autocard_role_count": str(len(autocard_data.roles)),
            "autocard_nature_count": str(len(autocard_data.natures)),
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading upstream SeerAPI database: %s", UPSTREAM_SEERAPI_URL)
    _download_file(UPSTREAM_SEERAPI_URL, OUTPUT_DB)
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
    logger.info("Loading official contract-partner data")
    pet_partner_data = _load_pet_partner_data()
    logger.info("Probing weekly preview image: %s", WEEKLY_PREVIEW_IMAGE_URL)
    weekly_preview_probe = _probe_weekly_preview_image()

    _merge_ironsbot_tables(
        OUTPUT_DB,
        config_data=config_data,
        autocard_data=autocard_data,
        item_exchange_prices=item_exchange_prices,
        effect_descriptions=effect_descriptions,
        pet_partner_data=pet_partner_data,
        weekly_preview_probe=weekly_preview_probe,
    )
    _quick_check(OUTPUT_DB)
    size_mb = OUTPUT_DB.stat().st_size / 1024 / 1024
    logger.info(
        (
            "Built %s (%.2f MB), mintmark_quality rows: %s, "
            "skin shop rows: %s, exchange price rows: %s, effect descriptions: %s, "
            "soulmark icons: %s, contract partners: %s, autocard cards: %s"
        ),
        OUTPUT_DB,
        size_mb,
        len(config_data.mintmark_quality),
        len(config_data.skin_shop_prices),
        len(item_exchange_prices),
        len(effect_descriptions),
        len(config_data.soulmark_icons),
        len(pet_partner_data.groups),
        len(autocard_data.cards),
    )


if __name__ == "__main__":
    main()
