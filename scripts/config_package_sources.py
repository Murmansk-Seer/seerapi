# SPDX-License-Identifier: MIT
"""Pure binary decoders for official ConfigPackage text assets."""

from __future__ import annotations

from dataclasses import dataclass
import struct


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
class SoulmarkIcon:
    soulmark_id: int
    pet_id: int
    effect_id: int
    icon_id: int


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
        return value - 256 if value > 127 else value

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


def parse_package_manifest(data: bytes) -> PackageManifestData:
    reader = BytesReader(data)
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
        for _ in range(reader.read_u16()):
            reader.read_i32()
        asset_refs.append((asset_path, bundle_index))

    bundles: list[BundleInfo] = []
    for _ in range(reader.read_i32()):
        name = reader.read_text()
        reader.read_u32()
        file_hash = reader.read_text()
        reader.read_text()
        file_size = reader.read_i64()
        reader.read_bool()
        reader.read_i8()
        for _ in range(reader.read_u16()):
            reader.read_i32()
        bundles.append(BundleInfo(name=name, file_hash=file_hash, file_size=file_size))

    assets = {
        asset_path: bundles[bundle_index]
        for asset_path, bundle_index in asset_refs
        if 0 <= bundle_index < len(bundles)
    }
    return PackageManifestData(bundles=tuple(bundles), assets=assets)


def parse_mintmark_quality(data: bytes) -> dict[int, int]:
    reader = BytesReader(data)
    if not reader.read_bool():
        return {}
    result: dict[int, int] = {}
    if reader.read_bool():
        for _ in range(reader.read_i32()):
            mintmark_id, quality = _read_mintmark_quality(reader)
            if mintmark_id > 0 and quality > 0:
                result[mintmark_id] = quality
    if reader.read_bool():
        for _ in range(reader.read_i32()):
            reader.read_text()
            reader.read_i32()
    return result


def parse_skin_store_pool(data: bytes) -> list[SkinStorePrice]:
    if not data:
        return []
    reader = BytesReader(data)
    if not reader.read_bool():
        return []
    result: list[SkinStorePrice] = []
    for _ in range(reader.read_i32()):
        reader.read_i32()
        price = reader.read_i32()
        original_price = reader.read_i32()
        discount_rate = reader.read_i32()
        end_time = reader.read_i32()
        reader.read_i32()
        selected_price = reader.read_i32()
        reader.read_i32()
        pool_id = reader.read_i32()
        for _ in range(4):
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


def parse_skin_shop(data: bytes) -> list[SkinShopPrice]:
    if not data:
        return []
    reader = BytesReader(data)
    if not reader.read_bool() or not reader.read_bool() or not reader.read_bool():
        return []
    result: list[SkinShopPrice] = []
    for _ in range(reader.read_i32()):
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
            for _ in range(reader.read_i32()):
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


def parse_items_tip(data: bytes) -> dict[int, str]:
    if not data:
        return {}
    reader = BytesReader(data)
    if not reader.read_bool() or not reader.read_bool():
        return {}
    result: dict[int, str] = {}
    for _ in range(reader.read_i32()):
        description = reader.read_text()
        item_id = reader.read_i32()
        result[item_id] = description
    return result


def parse_effect_icons(data: bytes) -> list[SoulmarkIcon]:
    if not data:
        return []
    reader = BytesReader(data)
    if not reader.read_bool() or not reader.read_bool():
        return []
    result: list[SoulmarkIcon] = []
    for _ in range(reader.read_i32()):
        soulmark_id = reader.read_i32()
        reader.read_text()
        reader.read_text()
        reader.read_text()
        _skip_optional_text_array(reader)
        effect_id = reader.read_i32()
        icon_id = reader.read_i32()
        reader.read_i32()
        reader.read_i32()
        _skip_optional_int_array(reader)
        reader.read_i32()
        reader.read_i32()
        pet_ids = _read_optional_int_array(reader)
        _skip_optional_int_array(reader)
        _skip_optional_text_array(reader)
        reader.read_i32()
        reader.read_text()
        reader.read_i32()
        reader.read_i32()
        if soulmark_id <= 0 or icon_id <= 0:
            continue
        result.extend(
            SoulmarkIcon(
                soulmark_id=soulmark_id,
                pet_id=pet_id,
                effect_id=effect_id,
                icon_id=icon_id,
            )
            for pet_id in (pet_ids or [0])
        )
    return result


def parse_autocard_season_effects(data: bytes) -> list[AutocardSeasonEffect]:
    if not data:
        return []
    reader = BytesReader(data)
    if not reader.read_bool():
        return []
    result: list[AutocardSeasonEffect] = []
    for _ in range(reader.read_i32()):
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


def _read_mintmark_quality(reader: BytesReader) -> tuple[int, int]:
    _skip_optional_int_array(reader)
    _skip_optional_int_array(reader)
    reader.read_i32()
    reader.read_text()
    reader.read_text()
    _skip_optional_int_array(reader)
    reader.read_i32()
    reader.read_i32()
    mintmark_id = reader.read_i32()
    reader.read_i32()
    reader.read_i32()
    _skip_optional_int_array(reader)
    reader.read_i32()
    _skip_optional_int_array(reader)
    _skip_optional_int_array(reader)
    quality = reader.read_i32()
    for _ in range(4):
        reader.read_i32()
    return mintmark_id, quality


def _read_optional_int_array(reader: BytesReader) -> list[int]:
    if not reader.read_bool():
        return []
    return [reader.read_i32() for _ in range(reader.read_i32())]


def _skip_optional_int_array(reader: BytesReader) -> None:
    _read_optional_int_array(reader)


def _skip_optional_text_array(reader: BytesReader) -> None:
    if not reader.read_bool():
        return
    for _ in range(reader.read_i32()):
        reader.read_text()
