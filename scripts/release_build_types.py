# SPDX-License-Identifier: MIT
"""Value objects shared by the SeerAPI release build boundaries."""

from __future__ import annotations

from dataclasses import dataclass

if __package__:
    from .config_package_sources import (
        AutocardSeasonEffect,
        SkinShopPrice,
        SkinStorePrice,
        SoulmarkIcon,
    )
else:
    from config_package_sources import (  # type: ignore[import-not-found]
        AutocardSeasonEffect,
        SkinShopPrice,
        SkinStorePrice,
        SoulmarkIcon,
    )


@dataclass(frozen=True, slots=True)
class ConfigPackageData:
    """Parsed ConfigPackage facts required by the public release."""

    version: str
    bundle_url: str
    mintmark_quality: dict[int, int]
    skin_store_prices: list[SkinStorePrice]
    skin_shop_prices: list[SkinShopPrice]
    skin_item_tips: dict[int, str]
    soulmark_icons: list[SoulmarkIcon]
    autocard_season_effects: list[AutocardSeasonEffect]
