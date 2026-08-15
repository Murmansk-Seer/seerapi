# SPDX-License-Identifier: MIT
"""Official source loaders used by the SeerAPI release build."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
import json
import logging
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

if __package__:
    from .build_http import BuildHttpClient, extract_text_assets
    from .config_package_sources import (
        parse_autocard_season_effects,
        parse_effect_icons,
        parse_items_tip,
        parse_mintmark_quality,
        parse_package_manifest,
        parse_skin_shop,
        parse_skin_store_pool,
    )
    from .effect_metadata_sources import (
        EffectDescription,
        SpecialEffectStatus,
        parse_effect_descriptions,
        parse_special_effect_statuses,
    )
    from .item_exchange_sources import (
        ItemExchangePrice,
        parse_commodity_shop,
        parse_special_skill_shop,
    )
    from .json_value_helpers import item_int, item_text
    from .partner_contract_sources import PetPartnerData, parse_pet_partner_data
    from .release_build_types import ConfigPackageData
else:
    from build_http import (  # type: ignore[import-not-found]
        BuildHttpClient,
        extract_text_assets,
    )
    from config_package_sources import (  # type: ignore[import-not-found]
        parse_autocard_season_effects,
        parse_effect_icons,
        parse_items_tip,
        parse_mintmark_quality,
        parse_package_manifest,
        parse_skin_shop,
        parse_skin_store_pool,
    )
    from effect_metadata_sources import (  # type: ignore[import-not-found]
        EffectDescription,
        SpecialEffectStatus,
        parse_effect_descriptions,
        parse_special_effect_statuses,
    )
    from item_exchange_sources import (  # type: ignore[import-not-found]
        ItemExchangePrice,
        parse_commodity_shop,
        parse_special_skill_shop,
    )
    from json_value_helpers import item_int, item_text  # type: ignore[import-not-found]
    from partner_contract_sources import (  # type: ignore[import-not-found]
        PetPartnerData,
        parse_pet_partner_data,
    )
    from release_build_types import ConfigPackageData  # type: ignore[import-not-found]


@dataclass(frozen=True, slots=True)
class ReleaseSourceConfig:
    config_package_base_url: str
    config_package_name: str
    config_bundle_name: str
    config_text_assets: set[str]
    mintmark_bytes_name: str
    skin_store_pool_bytes_name: str
    skin_shop_bytes_name: str
    items_tip_bytes_name: str
    effect_icon_bytes_name: str
    autocard_season_effect_bytes_name: str
    autocard_json_dir: str
    autocard_json_base_url: str
    unity_item_catalog_url: str
    battlepass_shop_url: str
    battlepass_shop_source_key: str
    battlepass_shop_source_name: str
    activity_shop_url: str
    activity_shop_source_key: str
    activity_shop_source_name: str
    special_skill_shop_url: str
    special_skill_shop_source_key: str
    special_skill_shop_source_name: str
    effect_description_url: str
    special_effect_status_url: str
    partner_contracts_url: str
    partner_contracts_schema_version: int
    partner_contract_group_type: str
    contract_badge_item_id: int
    contract_badge_item_name: str
    partner_contracts_descriptions_reversed: bool


class ReleaseSourceLoader:
    """Loads and parses official source data without publishing SQLite tables."""

    def __init__(
        self,
        http: BuildHttpClient,
        config: ReleaseSourceConfig,
        *,
        logger: logging.Logger,
    ) -> None:
        self._http = http
        self._config = config
        self._logger = logger

    def fetch_config_package_data(self) -> ConfigPackageData:
        base_url = self._config.config_package_base_url.rstrip("/") + "/"
        version, manifest = self._http.fetch_package_manifest(
            base_url,
            self._config.config_package_name,
            parse_manifest=parse_package_manifest,
        )
        bundle = next(
            (
                item
                for item in manifest.bundles
                if item.name == self._config.config_bundle_name
            ),
            None,
        )
        if bundle is None:
            if len(manifest.bundles) != 1:
                raise ValueError("ConfigPackage bundle not found")
            bundle = manifest.bundles[0]
        bundle_url = urljoin(base_url, bundle.file_hash)
        assets = extract_text_assets(
            self._http.download_bytes(bundle_url),
            self._config.config_text_assets,
        )
        return ConfigPackageData(
            version=version,
            bundle_url=bundle_url,
            mintmark_quality=parse_mintmark_quality(
                assets[self._config.mintmark_bytes_name]
            ),
            skin_store_prices=parse_skin_store_pool(
                assets[self._config.skin_store_pool_bytes_name]
            ),
            skin_shop_prices=parse_skin_shop(assets[self._config.skin_shop_bytes_name]),
            skin_item_tips=parse_items_tip(assets[self._config.items_tip_bytes_name]),
            soulmark_icons=parse_effect_icons(
                assets[self._config.effect_icon_bytes_name]
            ),
            autocard_season_effects=parse_autocard_season_effects(
                assets[self._config.autocard_season_effect_bytes_name]
            ),
        )

    def load_autocard_json(self, filename: str) -> tuple[dict[str, object], str]:
        if self._config.autocard_json_dir:
            path = Path(self._config.autocard_json_dir) / filename
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8")), str(path)
        url = urljoin(self._config.autocard_json_base_url.rstrip("/") + "/", filename)
        return json.loads(self._http.download_bytes(url).decode("utf-8-sig")), url

    def load_item_exchange_prices(self) -> list[ItemExchangePrice]:
        try:
            currency_names = _parse_unity_item_names(
                self._http.download_bytes(self._config.unity_item_catalog_url)
            )
        except _SOURCE_ERRORS as error:
            self._logger.warning(
                "Official Unity item names skipped: %s", _short_error(error)
            )
            currency_names = {}
        prices: list[ItemExchangePrice] = []
        for source_name, source_url, parser in self._item_exchange_sources():
            try:
                prices.extend(
                    replace(
                        item,
                        currency_name=currency_names.get(item.currency_item_id, ""),
                    )
                    for item in parser(self._http.download_bytes(source_url))
                )
            except _SOURCE_ERRORS as error:
                self._logger.warning(
                    "Item exchange price source skipped (%s): %s",
                    source_name,
                    _short_error(error),
                )
        return prices

    def load_effect_descriptions(self) -> list[EffectDescription]:
        return self._load_optional(
            "Effect description source",
            self._config.effect_description_url,
            parse_effect_descriptions,
        )

    def load_special_effect_statuses(self) -> list[SpecialEffectStatus]:
        return self._load_optional(
            "Special effect status source",
            self._config.special_effect_status_url,
            parse_special_effect_statuses,
        )

    def load_pet_partner_data(self) -> PetPartnerData:
        try:
            return parse_pet_partner_data(
                self._http.download_bytes(self._config.partner_contracts_url),
                schema_version=self._config.partner_contracts_schema_version,
                group_type=self._config.partner_contract_group_type,
                cost_item_id=self._config.contract_badge_item_id,
                cost_item_name=self._config.contract_badge_item_name,
                descriptions_reversed=(
                    self._config.partner_contracts_descriptions_reversed
                ),
            )
        except (*_SOURCE_ERRORS, ValueError) as error:
            self._logger.warning(
                "Official contract-partner source skipped: %s", _short_error(error)
            )
            return PetPartnerData(groups=[], upgrades=[])

    def _load_optional(
        self,
        label: str,
        url: str,
        parser: Callable[[bytes], list[Any]],
    ) -> list[Any]:
        try:
            return parser(self._http.download_bytes(url))
        except _SOURCE_ERRORS as error:
            self._logger.warning("%s skipped: %s", label, _short_error(error))
            return []

    def _item_exchange_sources(
        self,
    ) -> tuple[tuple[str, str, Callable[[bytes], list[ItemExchangePrice]]], ...]:
        config = self._config
        return (
            (
                config.battlepass_shop_source_name,
                config.battlepass_shop_url,
                partial(
                    parse_commodity_shop,
                    source_key=config.battlepass_shop_source_key,
                    source_name=config.battlepass_shop_source_name,
                ),
            ),
            (
                config.activity_shop_source_name,
                config.activity_shop_url,
                partial(
                    parse_commodity_shop,
                    source_key=config.activity_shop_source_key,
                    source_name=config.activity_shop_source_name,
                ),
            ),
            (
                config.special_skill_shop_source_name,
                config.special_skill_shop_url,
                partial(
                    parse_special_skill_shop,
                    source_key=config.special_skill_shop_source_key,
                    source_name=config.special_skill_shop_source_name,
                ),
            ),
        )


_SOURCE_ERRORS = (
    HTTPError,
    URLError,
    TimeoutError,
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
)


def _parse_unity_item_names(data: bytes) -> dict[int, str]:
    raw = json.loads(data.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Unity item catalog root must be an object")
    items_root = raw.get("root")
    if not isinstance(items_root, dict):
        raise ValueError("Unity item catalog has no root object")
    rows = items_root.get("items")
    if not isinstance(rows, list):
        raise ValueError("Unity item catalog has no items list")
    names: dict[int, str] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        item_id = item_int(row, "id")
        item_name = item_text(row, "name").strip()
        if item_id <= 0 or not item_name:
            continue
        existing = names.setdefault(item_id, item_name)
        if existing != item_name:
            raise ValueError(
                f"Unity item catalog has conflicting name for item {item_id} at index {index}"
            )
    return names


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]
