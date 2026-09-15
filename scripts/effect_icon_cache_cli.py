# SPDX-License-Identifier: MIT
"""CLI-oriented cache operations for pre-rendered effect icon PNGs."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class EffectIconCacheShardPlan:
    icon_ids: tuple[int, ...]
    cached_count: int
    repair_icon_ids: tuple[int, ...]

    @property
    def needs_render(self) -> bool:
        return bool(self.repair_icon_ids)


def add_effect_icon_cache_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--seed-effect-icon-cache",
        type=Path,
        metavar="DATABASE",
        help="restore matching effect icon PNGs from a previous SeerAPI SQLite database",
    )
    parser.add_argument(
        "--render-effect-icon-shard",
        type=int,
        metavar="INDEX",
        help="render one zero-based effect icon cache shard instead of building SQLite",
    )
    parser.add_argument(
        "--plan-effect-icon-shard",
        type=int,
        metavar="INDEX",
        help="inspect one zero-based effect icon cache shard without invoking FFDec",
    )
    parser.add_argument(
        "--effect-icon-shard-count",
        type=int,
        default=1,
        metavar="COUNT",
        help="total shard count used with an effect icon shard operation",
    )
    parser.add_argument(
        "--export-effect-icon-cache-shard",
        type=Path,
        metavar="DIRECTORY",
        help="output directory for the rendered shard cache",
    )
    parser.add_argument(
        "--effect-icon-shard-plan-output",
        type=Path,
        metavar="FILE",
        help="write GitHub-output-compatible shard plan values",
    )
    parser.add_argument(
        "--effect-icon-repair-ids",
        type=_parse_effect_icon_ids,
        metavar="ID,ID,...",
        help="ordered icon IDs selected by the shard plan for rendering",
    )
    parser.add_argument(
        "--effect-icon-shard-ids",
        type=_parse_effect_icon_ids,
        metavar="ID,ID,...",
        help="ordered full shard ID snapshot selected by the shard plan",
    )


def validate_effect_icon_cache_cli_arguments(
    parser: argparse.ArgumentParser,
    arguments: argparse.Namespace,
) -> None:
    shard_operations = sum(
        operation is not None
        for operation in (
            arguments.render_effect_icon_shard,
            arguments.plan_effect_icon_shard,
        )
    )
    if shard_operations > 1:
        parser.error(
            "--plan-effect-icon-shard and --render-effect-icon-shard are mutually exclusive"
        )
    if shard_operations == 0:
        if (
            arguments.effect_icon_shard_count != 1
            or arguments.export_effect_icon_cache_shard is not None
            or arguments.effect_icon_shard_plan_output is not None
            or arguments.effect_icon_repair_ids is not None
            or arguments.effect_icon_shard_ids is not None
        ):
            parser.error(
                "effect icon shard options require --plan-effect-icon-shard "
                "or --render-effect-icon-shard"
            )
        return
    if arguments.export_effect_icon_cache_shard is None:
        parser.error(
            "effect icon shard operations require --export-effect-icon-cache-shard"
        )
    if (
        arguments.plan_effect_icon_shard is not None
        and arguments.effect_icon_shard_plan_output is None
    ):
        parser.error(
            "--plan-effect-icon-shard requires --effect-icon-shard-plan-output"
        )
    if (
        arguments.render_effect_icon_shard is not None
        and arguments.effect_icon_shard_plan_output is not None
    ):
        parser.error(
            "--effect-icon-shard-plan-output requires --plan-effect-icon-shard"
        )
    if (
        arguments.render_effect_icon_shard is not None
        and (
            arguments.effect_icon_repair_ids is None
            or arguments.effect_icon_shard_ids is None
        )
    ):
        parser.error(
            "--render-effect-icon-shard requires --effect-icon-shard-ids "
            "and --effect-icon-repair-ids"
        )
    if (
        arguments.plan_effect_icon_shard is not None
        and (
            arguments.effect_icon_repair_ids is not None
            or arguments.effect_icon_shard_ids is not None
        )
    ):
        parser.error(
            "effect icon ID snapshots require --render-effect-icon-shard"
        )


def write_effect_icon_cache_shard_plan(
    plan: EffectIconCacheShardPlan,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            (
                f"needs_render={str(plan.needs_render).lower()}",
                f"icon_count={len(plan.icon_ids)}",
                f"cached_count={plan.cached_count}",
                f"repair_count={len(plan.repair_icon_ids)}",
                "shard_icon_ids=" + ",".join(map(str, plan.icon_ids)),
                "repair_icon_ids=" + ",".join(map(str, plan.repair_icon_ids)),
                "",
            )
        ),
        encoding="utf-8",
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
        logger.info("No previous SeerAPI database to seed effect icon PNG cache")
        return 0
    try:
        with sqlite3.connect(db_path) as conn:
            metadata_row = conn.execute(
                """
                SELECT value
                FROM seerapi_metadata
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
        "Seeded %s effect icon PNGs from previous SeerAPI database", seeded_count
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
    shard_icon_ids: Sequence[int],
    repair_icon_ids: Sequence[int],
    render_icons: Callable[[set[int]], Mapping[int, EffectIconPngRender]],
    export_cache: Callable[[Sequence[int], Path], int],
    logger: logging.Logger,
) -> tuple[int, int]:
    """Render and export one validated SWF-fallback icon cache shard."""
    _validate_effect_icon_shard_index(shard_index, shard_count)
    if len(set(shard_icon_ids)) != len(shard_icon_ids):
        raise ValueError("Effect icon shard IDs must be unique")
    selected_icon_ids = _select_effect_icon_repairs(
        shard_icon_ids=shard_icon_ids,
        repair_icon_ids=repair_icon_ids,
    )
    logger.info(
        "Rendering SWF fallback effect icon cache shard %s/%s: %s of %s icons",
        shard_index + 1,
        shard_count,
        len(selected_icon_ids),
        len(shard_icon_ids),
    )
    renders = render_icons(set(selected_icon_ids))
    export_cache(shard_icon_ids, output_dir)
    return len(selected_icon_ids), sum(
        1 for render in renders.values() if render.available
    )


def plan_effect_icon_png_cache_shard(
    *,
    shard_index: int,
    shard_count: int,
    output_dir: Path,
    fetch_icon_ids: Callable[[], set[int]],
    find_fallback_icon_ids: Callable[[set[int]], Sequence[int]],
    inspect_icons: Callable[
        [set[int]],
        tuple[
            Mapping[int, EffectIconAssetCheck],
            Mapping[int, EffectIconPngRender],
        ],
    ],
    export_cache: Callable[[Sequence[int], Path], int],
    logger: logging.Logger,
) -> EffectIconCacheShardPlan:
    """Inspect one shard and report only cache entries that require repair."""

    shard_icon_ids = _effect_icon_cache_shard_ids(
        shard_index=shard_index,
        shard_count=shard_count,
        icon_ids=find_fallback_icon_ids(fetch_icon_ids()),
    )
    checks, renders = inspect_icons(set(shard_icon_ids))
    repair_icon_ids = tuple(
        icon_id
        for icon_id in shard_icon_ids
        if _effect_icon_requires_repair(
            checks.get(icon_id),
            renders.get(icon_id),
        )
    )
    export_cache(shard_icon_ids, output_dir)
    cached_count = sum(
        bool(render is not None and render.available)
        for render in (renders.get(icon_id) for icon_id in shard_icon_ids)
    )
    logger.info(
        "Effect icon cache shard %s/%s: %s icons, %s cached, %s need repair",
        shard_index + 1,
        shard_count,
        len(shard_icon_ids),
        cached_count,
        len(repair_icon_ids),
    )
    return EffectIconCacheShardPlan(
        icon_ids=shard_icon_ids,
        cached_count=cached_count,
        repair_icon_ids=repair_icon_ids,
    )


def _effect_icon_cache_shard_ids(
    *,
    shard_index: int,
    shard_count: int,
    icon_ids: Sequence[int],
) -> tuple[int, ...]:
    _validate_effect_icon_shard_index(shard_index, shard_count)
    return tuple(icon_ids[shard_index::shard_count])


def _validate_effect_icon_shard_index(shard_index: int, shard_count: int) -> None:
    if shard_count <= 0:
        raise ValueError("Effect icon shard count must be positive")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError(
            f"Effect icon shard index must be in 0..{shard_count - 1}"
        )


def _effect_icon_requires_repair(
    check: EffectIconAssetCheck | None,
    render: EffectIconPngRender | None,
) -> bool:
    if check is None or render is None:
        return True
    return (check.available or check.status == 0) and not render.available


def _select_effect_icon_repairs(
    *,
    shard_icon_ids: Sequence[int],
    repair_icon_ids: Sequence[int],
) -> tuple[int, ...]:
    repair_id_set = set(repair_icon_ids)
    if len(repair_id_set) != len(repair_icon_ids):
        raise ValueError("Effect icon repair IDs must be unique")
    unknown_icon_ids = repair_id_set.difference(shard_icon_ids)
    if unknown_icon_ids:
        unknown = ", ".join(map(str, sorted(unknown_icon_ids)))
        raise ValueError(f"Effect icon repair IDs are outside the shard: {unknown}")
    return tuple(icon_id for icon_id in shard_icon_ids if icon_id in repair_id_set)


def _parse_effect_icon_ids(value: str) -> tuple[int, ...]:
    try:
        icon_ids = tuple(int(item) for item in value.split(",") if item)
    except ValueError as error:
        raise argparse.ArgumentTypeError("effect icon IDs must be integers") from error
    if not icon_ids:
        raise argparse.ArgumentTypeError("at least one effect icon ID is required")
    if any(icon_id <= 0 for icon_id in icon_ids):
        raise argparse.ArgumentTypeError("effect icon IDs must be positive")
    if len(set(icon_ids)) != len(icon_ids):
        raise argparse.ArgumentTypeError("effect icon IDs must be unique")
    return icon_ids


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]
