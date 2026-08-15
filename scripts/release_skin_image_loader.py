# SPDX-License-Identifier: MIT
"""Database-backed classic skin image source discovery and verification."""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3

if __package__:
    from .skin_image_asset_probe import SkinImageAssetProbe
    from .skin_image_resolution import (
        PET_IMAGE_ASSET_KINDS,
        ClassicSkinImageSource,
        PetImageSource,
        SkinImageResolution,
        content_hash_keys_for_classic_skin_fallbacks,
        resolve_classic_skin_image_resources,
        source_asset_keys_for_classic_skin_fallbacks,
    )
else:
    from skin_image_asset_probe import (
        SkinImageAssetProbe,  # type: ignore[import-not-found]
    )
    from skin_image_resolution import (  # type: ignore[import-not-found]
        PET_IMAGE_ASSET_KINDS,
        ClassicSkinImageSource,
        PetImageSource,
        SkinImageResolution,
        content_hash_keys_for_classic_skin_fallbacks,
        resolve_classic_skin_image_resources,
        source_asset_keys_for_classic_skin_fallbacks,
    )


def build_classic_skin_image_resolutions(
    db_path: Path,
    *,
    classic_skin_category_id: int,
    asset_probe: SkinImageAssetProbe,
    logger: logging.Logger,
) -> list[SkinImageResolution]:
    """Resolve direct and fallback body/head assets for classic skin rows."""
    with sqlite3.connect(db_path) as conn:
        skins = _load_classic_skins(conn, classic_skin_category_id)
        skin_names = {skin.name for skin in skins}
        pets = _load_named_pets(conn, skin_names)

    direct_keys = {
        (kind, skin.resource_id) for skin in skins for kind in PET_IMAGE_ASSET_KINDS
    }
    checks = asset_probe.verify_assets(direct_keys)
    source_keys = source_asset_keys_for_classic_skin_fallbacks(skins, pets, checks)
    checks.update(asset_probe.verify_assets(source_keys - checks.keys()))
    hash_asset_keys = content_hash_keys_for_classic_skin_fallbacks(skins, pets, checks)
    asset_hashes = {
        asset_key: asset_hash
        for asset_key in hash_asset_keys
        for check in (checks[asset_key],)
        if check.available
        and (asset_hash := asset_probe.download_asset_hash(check)) is not None
    }
    resolutions = resolve_classic_skin_image_resources(
        skins,
        pets,
        checks,
        asset_hashes,
    )
    fallback_count = sum(
        1
        for item in resolutions
        if item.head_resolution != "direct_skin"
        or item.body_resolution != "direct_skin"
    )
    unresolved_count = sum(
        1
        for item in resolutions
        if item.head_resolution in {"unresolved", "unverified"}
        or item.body_resolution in {"unresolved", "unverified"}
    )
    logger.info(
        "Resolved classic skin images: %s rows, %s with fallback, %s unresolved",
        len(resolutions),
        fallback_count,
        unresolved_count,
    )
    return resolutions


def _load_classic_skins(
    conn: sqlite3.Connection,
    category_id: int,
) -> tuple[ClassicSkinImageSource, ...]:
    rows = conn.execute(
        """
        SELECT id, name, resource_id
        FROM pet_skin
        WHERE category_id = ?
        ORDER BY id
        """,
        (category_id,),
    ).fetchall()
    return tuple(
        ClassicSkinImageSource(
            skin_id=int(skin_id),
            name=str(name).strip(),
            resource_id=int(resource_id),
        )
        for skin_id, name, resource_id in rows
        if int(resource_id) > 0 and str(name).strip()
    )


def _load_named_pets(
    conn: sqlite3.Connection,
    skin_names: set[str],
) -> tuple[PetImageSource, ...]:
    rows = conn.execute(
        """
        SELECT id, name, resource_id
        FROM pet
        WHERE resource_id > 0
        ORDER BY id
        """
    ).fetchall()
    return tuple(
        PetImageSource(
            pet_id=int(pet_id),
            name=str(name).strip(),
            resource_id=int(resource_id),
        )
        for pet_id, name, resource_id in rows
        if str(name).strip() in skin_names
    )
