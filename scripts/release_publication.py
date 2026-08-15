# SPDX-License-Identifier: MIT
"""Final SQLite publication transaction for the SeerAPI release build."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any

from solaris.analyze.output.pet_special_effect_facts import (
    replace_pet_special_effect_facts,
)

if __package__:
    from .autocard_sources import AutocardData
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconPngRender,
        SoulmarkIconRenderIssue,
    )
    from .effect_metadata_sources import EffectDescription, SpecialEffectStatus
    from .item_exchange_sources import ItemExchangePrice
    from .partner_contract_sources import PetPartnerData
    from .release_autocard_tables import (
        replace_autocard_season_effect_table,
        replace_autocard_tables,
    )
    from .release_build_types import ConfigPackageData
    from .release_config_tables import replace_config_package_tables
    from .release_metadata import build_release_metadata, replace_release_metadata
    from .release_partner_tables import replace_pet_partner_tables
    from .release_reference_tables import replace_reference_tables
    from .release_render_manifest_tables import (
        replace_render_asset_manifest_table,
    )
    from .release_soulmark_icon_tables import replace_soulmark_icon_tables
    from .render_asset_manifest_build import (
        build_render_asset_manifest,
        collect_remote_asset_manifest,
    )
    from .skin_image_resolution import SkinImageResolution
else:
    from autocard_sources import AutocardData  # type: ignore[import-not-found]
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconPngRender,
        SoulmarkIconRenderIssue,
    )
    from effect_metadata_sources import (  # type: ignore[import-not-found]
        EffectDescription,
        SpecialEffectStatus,
    )
    from item_exchange_sources import (
        ItemExchangePrice,  # type: ignore[import-not-found]
    )
    from partner_contract_sources import (
        PetPartnerData,  # type: ignore[import-not-found]
    )
    from release_autocard_tables import (  # type: ignore[import-not-found]
        replace_autocard_season_effect_table,
        replace_autocard_tables,
    )
    from release_build_types import ConfigPackageData  # type: ignore[import-not-found]
    from release_config_tables import (
        replace_config_package_tables,  # type: ignore[import-not-found]
    )
    from release_metadata import (  # type: ignore[import-not-found]
        build_release_metadata,
        replace_release_metadata,
    )
    from release_partner_tables import (
        replace_pet_partner_tables,  # type: ignore[import-not-found]
    )
    from release_reference_tables import (
        replace_reference_tables,  # type: ignore[import-not-found]
    )
    from release_render_manifest_tables import (  # type: ignore[import-not-found]
        replace_render_asset_manifest_table,
    )
    from release_soulmark_icon_tables import (
        replace_soulmark_icon_tables,  # type: ignore[import-not-found]
    )
    from render_asset_manifest_build import (  # type: ignore[import-not-found]
        build_render_asset_manifest,
        collect_remote_asset_manifest,
    )
    from skin_image_resolution import (
        SkinImageResolution,  # type: ignore[import-not-found]
    )


@dataclass(frozen=True, slots=True)
class ReleasePublicationInput:
    """Completed source facts that are published in one SQLite transaction."""

    config_data: ConfigPackageData
    autocard_data: AutocardData
    item_exchange_prices: list[ItemExchangePrice]
    effect_descriptions: list[EffectDescription]
    special_effect_statuses: list[SpecialEffectStatus]
    pet_partner_data: PetPartnerData
    weekly_preview_probe: dict[str, str]
    skin_image_resolutions: list[SkinImageResolution]


@dataclass(frozen=True, slots=True)
class ReleasePublicationContext:
    """Narrow adapters and immutable settings needed by publication."""

    load_asset_repository_snapshot: Callable[[], Any]
    resolve_effect_icons: Callable[[set[int]], Any]
    render_asset_manifest_config: Any
    effect_icon_cache_version: str
    metadata_context: Any
    logger: logging.Logger


def _collect_soulmark_icon_render_issues(
    soulmark_icons: list[tuple[int, int, int, int]],
    asset_checks: Mapping[int, EffectIconAssetCheck],
    png_renders: Mapping[int, EffectIconPngRender],
    pet_names: Mapping[int, str],
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


def publish_release_tables(
    db_path: Path,
    *,
    release: ReleasePublicationInput,
    context: ReleasePublicationContext,
) -> None:
    """Publish all IronsBot extension tables from already loaded release facts."""
    now = time.time()
    asset_repository_snapshot = context.load_asset_repository_snapshot()
    with sqlite3.connect(db_path) as conn:
        replace_config_package_tables(
            conn,
            release.config_data,
            release.skin_image_resolutions,
            now=now,
        )
        replace_reference_tables(
            conn,
            item_exchange_prices=release.item_exchange_prices,
            effect_descriptions=release.effect_descriptions,
            special_effect_statuses=release.special_effect_statuses,
            now=now,
        )
        remote_asset_manifest = collect_remote_asset_manifest(
            conn,
            asset_repository_snapshot,
            release_revision=release.config_data.version,
            config=context.render_asset_manifest_config,
        )
        soulmark_icons = sorted(
            {
                (item.soulmark_id, item.pet_id, item.effect_id, item.icon_id)
                for item in release.config_data.soulmark_icons
            }
        )
        effect_icon_resolution = context.resolve_effect_icons(
            {icon_id for _, _, _, icon_id in soulmark_icons}
        )
        asset_checks = effect_icon_resolution.asset_checks
        png_renders = effect_icon_resolution.png_renders
        render_manifest_build = build_render_asset_manifest(
            remote_asset_manifest,
            {
                icon_id: render.data if render.available else None
                for icon_id, render in png_renders.items()
                if icon_id in asset_checks
            },
            asset_repository_snapshot,
            release_revision=release.config_data.version,
            effect_icon_source_version=context.effect_icon_cache_version,
            config=context.render_asset_manifest_config,
        )
        issue_pet_ids = sorted(
            {
                pet_id
                for _, pet_id, _, icon_id in soulmark_icons
                if not png_renders[icon_id].available
            }
        )
        pet_names = _load_pet_names(conn, issue_pet_ids)
        render_issues = _collect_soulmark_icon_render_issues(
            soulmark_icons,
            asset_checks,
            png_renders,
            pet_names,
        )
        replace_soulmark_icon_tables(
            conn,
            soulmark_icons=soulmark_icons,
            asset_checks=asset_checks,
            png_renders=png_renders,
            render_issues=render_issues,
            now=now,
        )
        replace_render_asset_manifest_table(
            conn,
            render_manifest_build.entries,
            updated_at=now,
        )
        replace_autocard_tables(conn, release.autocard_data, now)
        replace_autocard_season_effect_table(
            conn,
            release.config_data.autocard_season_effects,
            now,
        )
        replace_pet_partner_tables(conn, release.pet_partner_data, updated_at=now)
        special_effect_facts = replace_pet_special_effect_facts(conn, now=now)
        metadata = build_release_metadata(
            context=context.metadata_context,
            built_at=now,
            config_data=release.config_data,
            effect_icon_resolution=effect_icon_resolution,
            effect_icon_asset_checks=asset_checks,
            effect_icon_png_renders=png_renders,
            effect_icon_render_issue_count=len(render_issues),
            render_manifest_metadata=render_manifest_build.metadata,
            skin_image_resolutions=release.skin_image_resolutions,
            item_exchange_prices=release.item_exchange_prices,
            effect_descriptions=release.effect_descriptions,
            special_effect_statuses=release.special_effect_statuses,
            special_effect_facts=special_effect_facts,
            pet_partner_data=release.pet_partner_data,
            soulmark_icon_count=len(soulmark_icons),
            autocard_data=release.autocard_data,
            weekly_preview_probe=release.weekly_preview_probe,
        )
        replace_release_metadata(conn, metadata)
        conn.commit()


def _load_pet_names(conn: sqlite3.Connection, pet_ids: list[int]) -> dict[int, str]:
    if not pet_ids:
        return {}
    placeholders = ", ".join("?" for _ in pet_ids)
    return {
        int(pet_id): str(name)
        for pet_id, name in conn.execute(
            f"SELECT id, name FROM pet WHERE id IN ({placeholders})",
            pet_ids,
        )
    }
