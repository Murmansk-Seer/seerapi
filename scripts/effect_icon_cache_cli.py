# SPDX-License-Identifier: MIT
"""CLI-oriented cache operations for pre-rendered effect icon PNGs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import logging
from pathlib import Path
import shutil
import sqlite3

if __package__:
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
    )
    from .effect_icon_png_renderer import (
        effect_icon_png_cache_metadata_path,
        effect_icon_png_cache_path,
        save_effect_icon_png_cache,
    )
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
    )
    from effect_icon_png_renderer import (  # type: ignore[import-not-found]
        effect_icon_png_cache_metadata_path,
        effect_icon_png_cache_path,
        save_effect_icon_png_cache,
    )


def seed_effect_icon_png_cache_from_database(
    db_path: Path,
    *,
    cache_version: str,
    icon_table: str,
    config: EffectIconBuildConfig,
    effect_icon_url: Callable[[int], str],
    logger: logging.Logger,
) -> int:
    """Seed the current renderer cache from compatible published PNG rows."""
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
            if metadata_row is None or metadata_row[0] != cache_version:
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
                FROM {icon_table}
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
            url=effect_icon_url(int(icon_id)),
            available=True,
            status=200,
            content_type=str(content_type),
            content_length=int(content_length),
            error="",
        )
        if save_effect_icon_png_cache(
            int(icon_id), png_data, check, config=config, logger=logger
        ):
            seeded_count += 1
    logger.info(
        "Seeded %s effect icon PNGs from previous IronsBot database", seeded_count
    )
    return seeded_count


def export_effect_icon_png_cache_shard(
    icon_ids: Sequence[int],
    output_dir: Path,
    *,
    cache_version: str,
    config: EffectIconBuildConfig,
    logger: logging.Logger,
) -> int:
    """Copy rendered cache entries for one CI shard into its publish directory."""
    exported_count = 0
    target_dir = output_dir / cache_version
    target_dir.mkdir(parents=True, exist_ok=True)
    for icon_id in icon_ids:
        source_path = effect_icon_png_cache_path(icon_id, config=config)
        metadata_path = effect_icon_png_cache_metadata_path(icon_id, config=config)
        if not source_path.is_file() or not metadata_path.is_file():
            continue
        shutil.copy2(source_path, target_dir / source_path.name)
        shutil.copy2(metadata_path, target_dir / metadata_path.name)
        exported_count += 1
    logger.info(
        "Exported %s effect icon PNG cache entries to %s", exported_count, output_dir
    )
    return exported_count


def render_effect_icon_png_cache_shard(
    *,
    shard_index: int,
    shard_count: int,
    output_dir: Path,
    fetch_icon_ids: Callable[[], set[int]],
    find_fallback_icon_ids: Callable[[set[int]], Sequence[int]],
    render_icons: Callable[[set[int]], Mapping[int, EffectIconPngRender]],
    export_cache: Callable[[Sequence[int], Path], int],
    logger: logging.Logger,
) -> tuple[int, int]:
    """Render and export one validated SWF-fallback icon cache shard."""
    if shard_count <= 0:
        raise ValueError("Effect icon shard count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(
            f"Effect icon shard index must be in 0..{shard_count - 1}"
        )
    fallback_icon_ids = list(find_fallback_icon_ids(fetch_icon_ids()))
    shard_icon_ids = fallback_icon_ids[shard_index::shard_count]
    logger.info(
        "Rendering SWF fallback effect icon cache shard %s/%s: %s icons",
        shard_index + 1,
        shard_count,
        len(shard_icon_ids),
    )
    renders = render_icons(set(shard_icon_ids))
    export_cache(shard_icon_ids, output_dir)
    return len(shard_icon_ids), sum(
        1 for render in renders.values() if render.available
    )


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]
