# SPDX-License-Identifier: MIT
"""Build the IronsBot full Seer SQLite database.

The runtime bot downloads this database as its main data source. The upstream
SeerAPI database is used only as build input here; custom IronsBot-only fields
are merged into the final SQLite file before it is published.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import sqlite3
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DB = ROOT / os.environ.get("IRONSBOT_DATA_OUTPUT", "ironsbot-data.sqlite")
UPSTREAM_SEERAPI_URL = os.environ.get(
    "IRONSBOT_DATA_UPSTREAM_SEERAPI_URL",
    "https://github.com/Murmansk5000/seer-data/releases/download/latest/seerapi-data.sqlite",
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
CONFIG_TEXT_ASSETS = {
    MINTMARK_BYTES_NAME,
    SKIN_STORE_POOL_BYTES_NAME,
    SKIN_SHOP_BYTES_NAME,
    ITEMS_TIP_BYTES_NAME,
}
MINTMARK_QUALITY_TABLE = "mintmark_quality"
SKIN_STORE_PRICE_TABLE = "skin_store_price"
SKIN_SHOP_PRICE_TABLE = "skin_shop_price"
SKIN_ITEM_TIP_TABLE = "skin_item_tip"
AUTOCARD_CARD_TABLE = "autocard_card"
AUTOCARD_ROLE_TABLE = "autocard_role"
AUTOCARD_NATURE_TABLE = "autocard_nature"
AUTOCARD_JSON_DIR = os.environ.get("IRONSBOT_DATA_AUTOCARD_JSON_DIR", "")
AUTOCARD_JSON_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_AUTOCARD_JSON_BASE_URL",
    "https://raw.githubusercontent.com/Murmansk5000/seer-unity-config-parser/main/json/",
)
AUTOCARD_CONTENT_FILE = "autocardContent.json"
AUTOCARD_NATURE_FILE = "autocardNature.json"
AUTOCARD_ROLE_FILE = "autocardRole.json"
WEEKLY_PREVIEW_IMAGE_URL = (
    "https://cnb.cool/HurryWang/seer-unity-preview-img-dumper-cnb/-/git/raw/"
    "master/img/preview.png"
)
WEEKLY_PREVIEW_SOURCE_URL = (
    "https://github.com/WhY15w/seer-unity-preview-img-dumper"
)
SIGNED_BYTE_MAX = 127
SIGNED_BYTE_MOD = 256
HTTP_TIMEOUT_SECONDS = 180
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


def _request(url: str, *, method: str | None = None) -> Request:
    return Request(
        url,
        headers={"User-Agent": "IronsBot data builder"},
        method=method,
    )


def _download_bytes(url: str) -> bytes:
    with urlopen(_request(url), timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read()


def _download_file(url: str, path: Path) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    with (
        urlopen(_request(url), timeout=HTTP_TIMEOUT_SECONDS) as response,
        tmp_path.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)
    tmp_path.replace(path)


def _probe_weekly_preview_image() -> dict[str, str]:
    try:
        with urlopen(
            _request(WEEKLY_PREVIEW_IMAGE_URL, method="HEAD"),
            timeout=HTTP_TIMEOUT_SECONDS,
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

    raise ValueError("ConfigPackage bundle not found")  # noqa: TRY003


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
        raise ValueError(  # noqa: TRY003
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


def _dump_json(item: dict[str, object]) -> str:
    return json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def _quick_check(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        result = conn.execute("PRAGMA quick_check").fetchone()
    if not result or result[0] != "ok":
        raise sqlite3.DatabaseError(  # noqa: TRY003
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


def _merge_ironsbot_tables(
    db_path: Path,
    *,
    config_data: ConfigPackageData,
    autocard_data: AutocardData,
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
        _replace_autocard_tables(conn, autocard_data, now)
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
            "mintmark_quality_count": str(len(config_data.mintmark_quality)),
            "skin_store_price_count": str(len(config_data.skin_store_prices)),
            "skin_shop_price_count": str(len(config_data.skin_shop_prices)),
            "skin_item_tip_count": str(len(config_data.skin_item_tips)),
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
        raise ValueError("mintmark Quality map is empty")  # noqa: TRY003
    logger.info(
        "Loading autocard JSON data: %s",
        AUTOCARD_JSON_DIR or AUTOCARD_JSON_BASE_URL,
    )
    autocard_data = _load_autocard_data()
    logger.info("Probing weekly preview image: %s", WEEKLY_PREVIEW_IMAGE_URL)
    weekly_preview_probe = _probe_weekly_preview_image()

    _merge_ironsbot_tables(
        OUTPUT_DB,
        config_data=config_data,
        autocard_data=autocard_data,
        weekly_preview_probe=weekly_preview_probe,
    )
    _quick_check(OUTPUT_DB)
    size_mb = OUTPUT_DB.stat().st_size / 1024 / 1024
    logger.info(
        (
            "Built %s (%.2f MB), mintmark_quality rows: %s, "
            "skin shop rows: %s, autocard cards: %s"
        ),
        OUTPUT_DB,
        size_mb,
        len(config_data.mintmark_quality),
        len(config_data.skin_shop_prices),
        len(autocard_data.cards),
    )


if __name__ == "__main__":
    main()
