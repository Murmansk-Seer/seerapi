# SPDX-License-Identifier: MIT
"""Metadata projection and persistence for the published SeerAPI database."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import sqlite3
from typing import Any


@dataclass(frozen=True, slots=True)
class ReleaseMetadataContext:
    schema_contract_version_key: str
    schema_contract_version: str
    upstream_seerapi_url: str
    config_package_base_url: str
    effect_icon_asset_base_url: str
    effect_icon_asset_suffix: str
    effect_icon_prefer_flash: bool
    effect_icon_unity_png_enabled: bool
    default_package_base_url: str
    effect_icon_png_render_enabled: bool
    effect_icon_png_java_command: str
    effect_icon_png_ffdec_jar: str
    effect_icon_png_cache_version: str
    effect_icon_png_render_zoom: int
    item_exchange_source_urls: tuple[str, ...]
    effect_description_url: str
    special_effect_status_url: str
    partner_contracts_url: str
    weekly_preview_image_url: str
    weekly_preview_source_url: str


def build_release_metadata(
    *,
    context: ReleaseMetadataContext,
    built_at: float,
    config_data: Any,
    effect_icon_resolution: Any,
    effect_icon_asset_checks: Mapping[int, Any],
    effect_icon_png_renders: Mapping[int, Any],
    effect_icon_render_issue_count: int,
    render_manifest_metadata: Mapping[str, str],
    skin_image_resolutions: Sequence[Any],
    item_exchange_prices: Sequence[Any],
    effect_descriptions: Sequence[Any],
    special_effect_statuses: Sequence[Any],
    special_effect_facts: Any,
    pet_partner_data: Any,
    soulmark_icon_count: int,
    autocard_data: Any,
    weekly_preview_probe: Mapping[str, str],
) -> dict[str, str]:
    """Build the stable public metadata contract from completed release facts."""
    return {
        context.schema_contract_version_key: context.schema_contract_version,
        "built_at": str(int(built_at)),
        "upstream_seerapi_url": context.upstream_seerapi_url,
        "config_package_base_url": context.config_package_base_url,
        "config_package_version": config_data.version,
        "config_bundle_url": config_data.bundle_url,
        "effect_icon_asset_base_url": context.effect_icon_asset_base_url,
        "effect_icon_asset_suffix": context.effect_icon_asset_suffix,
        "effect_icon_prefer_flash": str(int(context.effect_icon_prefer_flash)),
        "effect_icon_primary_source": effect_icon_resolution.preferred_source,
        "effect_icon_unity_png_enabled": str(
            int(context.effect_icon_unity_png_enabled)
        ),
        "effect_icon_unity_package_base_url": context.default_package_base_url,
        "effect_icon_unity_package_version": effect_icon_resolution.unity_package_version,
        "effect_icon_unity_manifest_icon_count": str(
            effect_icon_resolution.unity_manifest_icon_count
        ),
        "effect_icon_unity_png_available_count": str(
            effect_icon_resolution.unity_png_available_count
        ),
        "effect_icon_unity_png_missing_count": str(
            len(effect_icon_resolution.unity_missing_icon_ids)
        ),
        "effect_icon_unity_png_missing_ids": ",".join(
            str(icon_id) for icon_id in effect_icon_resolution.unity_missing_icon_ids
        ),
        "effect_icon_flash_png_available_count": str(
            effect_icon_resolution.flash_png_available_count
        ),
        "effect_icon_flash_png_missing_count": str(
            len(effect_icon_resolution.flash_missing_icon_ids)
        ),
        "effect_icon_flash_png_missing_ids": ",".join(
            str(icon_id) for icon_id in effect_icon_resolution.flash_missing_icon_ids
        ),
        "effect_icon_unity_fallback_icon_count": str(
            effect_icon_resolution.unity_fallback_icon_count
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
            sum(1 for check in effect_icon_asset_checks.values() if not check.available)
        ),
        "effect_icon_png_render_enabled": str(
            int(context.effect_icon_png_render_enabled)
        ),
        "effect_icon_png_renderer": "ffdec-swf+unity-defaultpackage-png",
        "effect_icon_png_resolution_order": (
            "ffdec-swf,unity-defaultpackage-png"
            if context.effect_icon_prefer_flash
            else "unity-defaultpackage-png,ffdec-swf"
        ),
        "effect_icon_png_render_java_command": context.effect_icon_png_java_command,
        "effect_icon_png_render_ffdec_jar": context.effect_icon_png_ffdec_jar,
        "effect_icon_png_cache_version": context.effect_icon_png_cache_version,
        "effect_icon_png_render_zoom": str(context.effect_icon_png_render_zoom),
        "effect_icon_png_render_checked_count": str(len(effect_icon_png_renders)),
        "effect_icon_png_render_available_count": str(
            sum(1 for render in effect_icon_png_renders.values() if render.available)
        ),
        "effect_icon_png_render_missing_count": str(
            sum(1 for render in effect_icon_png_renders.values() if not render.available)
        ),
        "effect_icon_png_render_issue_row_count": str(effect_icon_render_issue_count),
        **render_manifest_metadata,
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
            context.item_exchange_source_urls
        ),
        "effect_description_count": str(len(effect_descriptions)),
        "effect_description_source_url": context.effect_description_url,
        "special_effect_status_count": str(len(special_effect_statuses)),
        "special_effect_status_source_url": context.special_effect_status_url,
        "pet_special_effect_count": str(special_effect_facts.facts),
        "pet_special_effect_source_count": str(special_effect_facts.sources),
        "pet_special_effect_issue_count": str(special_effect_facts.issues),
        "pet_soulmark_display_count": str(special_effect_facts.soulmark_display_rows),
        "pet_soulmark_display_addition_count": str(
            special_effect_facts.soulmark_display_addition_rows
        ),
        "pet_partner_group_count": str(len(pet_partner_data.groups)),
        "pet_partner_upgrade_count": str(len(pet_partner_data.upgrades)),
        "pet_partner_source_url": context.partner_contracts_url,
        "soulmark_icon_count": str(soulmark_icon_count),
        "autocard_card_count": str(len(autocard_data.cards)),
        "autocard_role_count": str(len(autocard_data.roles)),
        "autocard_nature_count": str(len(autocard_data.natures)),
        "autocard_buff_count": str(len(autocard_data.buffs)),
        "autocard_season_effect_count": str(len(config_data.autocard_season_effects)),
        "autocard_source": autocard_data.source,
        "weekly_preview_image_url": context.weekly_preview_image_url,
        "weekly_preview_source_url": context.weekly_preview_source_url,
        **weekly_preview_probe,
    }


def replace_release_metadata(
    conn: sqlite3.Connection,
    metadata: Mapping[str, str],
) -> None:
    """Upsert the complete public metadata projection for one release."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seerapi_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO seerapi_metadata (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        sorted(metadata.items()),
    )
