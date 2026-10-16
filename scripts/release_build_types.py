# SPDX-License-Identifier: MIT
"""Value objects shared by the SeerAPI release build boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field

if __package__:
    from .config_package_sources import (
        AutocardChip,
        AutocardSeasonEffect,
        SkinShopPrice,
        SkinStorePrice,
        SoulmarkIcon,
    )
    from .release_peak_sources import OfficialPeakData
else:
    from config_package_sources import (  # type: ignore[import-not-found]
        AutocardChip,
        AutocardSeasonEffect,
        SkinShopPrice,
        SkinStorePrice,
        SoulmarkIcon,
    )
    from release_peak_sources import OfficialPeakData


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
    autocard_chips: list[AutocardChip] = field(default_factory=list)
    peak: OfficialPeakData | None = None
