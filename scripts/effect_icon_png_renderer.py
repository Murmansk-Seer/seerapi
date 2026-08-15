# SPDX-License-Identifier: MIT
"""Build-time FFDec rendering and cache management for effect icon PNGs.

This module deliberately owns every process and filesystem operation needed to
turn a verified Flash effect icon into a release PNG.  Source discovery stays
with the build orchestrator; the runtime bot never imports this module.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, UnidentifiedImageError

if __package__:
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
    )
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
    )


DownloadEffectIcon = Callable[[EffectIconAssetCheck], bytes]


def _short_error(error: BaseException, *, limit: int = 240) -> str:
    text = str(error).replace("\n", " ").strip()
    return text[:limit] if text else type(error).__name__


def visible_png_pixel_count(data: bytes, *, config: EffectIconBuildConfig) -> int:
    """Validate a PNG and return its number of non-transparent pixels."""

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("renderer output is not PNG")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            if max(image.size) > config.max_png_dimension:
                raise ValueError(
                    "renderer output dimensions exceed "
                    f"{config.max_png_dimension}px: {image.size}"
                )
            alpha_histogram = image.convert("RGBA").getchannel("A").histogram()
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError(f"renderer output is an invalid PNG: {error}") from error
    return sum(alpha_histogram[1:])


def _run_ffdec_command(
    args: list[str],
    *,
    timeout_seconds: float,
) -> None:
    completed = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode == 0:
        return
    message = (completed.stderr or "").strip() or (completed.stdout or "").strip()
    raise RuntimeError(f"FFDec exited {completed.returncode}: {message}")


def _select_visible_png(
    output_dir: Path,
    *,
    config: EffectIconBuildConfig,
    prefer_item_sprite: bool = False,
) -> bytes:
    candidates: list[tuple[int, bytes, Path]] = []
    invalid_errors: list[str] = []
    for png_path in sorted(output_dir.rglob("*.png")):
        png_data = png_path.read_bytes()
        try:
            visible_pixels = visible_png_pixel_count(png_data, config=config)
        except ValueError as error:
            invalid_errors.append(f"{png_path.name}: {error}")
            continue
        if visible_pixels > 0:
            candidates.append((visible_pixels, png_data, png_path))
        else:
            invalid_errors.append(f"{png_path.name}: fully transparent")
    if prefer_item_sprite:
        item_candidates = [
            candidate
            for candidate in candidates
            if any(part.endswith("_item") for part in candidate[2].parts)
        ]
        if item_candidates:
            candidates = item_candidates
    if not candidates:
        details = "; ".join(invalid_errors[:5]) or "no PNG files exported"
        raise ValueError(f"FFDec produced no visible PNG: {details}")
    _, png_data, _ = max(
        candidates,
        key=lambda candidate: (candidate[0], len(candidate[1])),
    )
    return png_data


def _render_full_effect_icon_png(
    swf_path: Path,
    temp_path: Path,
    *,
    config: EffectIconBuildConfig,
) -> bytes:
    output_dir = temp_path / "sprites"
    output_dir.mkdir()
    _run_ffdec_command(
        [
            config.java_command,
            "-jar",
            str(config.ffdec_jar),
            "-zoom",
            str(config.render_zoom),
            "-ignorebackground",
            "-format",
            "sprite:png",
            "-export",
            "sprite",
            str(output_dir),
            str(swf_path),
        ],
        timeout_seconds=config.composite_render_timeout_seconds,
    )
    return _select_visible_png(
        output_dir,
        config=config,
        prefer_item_sprite=True,
    )


def _render_shape_effect_icon_png(
    swf_path: Path,
    temp_path: Path,
    *,
    config: EffectIconBuildConfig,
) -> bytes:
    output_dir = temp_path / "shapes"
    output_dir.mkdir()
    _run_ffdec_command(
        [
            config.java_command,
            "-jar",
            str(config.ffdec_jar),
            "-zoom",
            str(config.render_zoom),
            "-format",
            "shape:png",
            "-export",
            "shape",
            str(output_dir),
            str(swf_path),
        ],
        timeout_seconds=config.shape_render_timeout_seconds,
    )
    return _select_visible_png(output_dir, config=config)


def effect_icon_png_cache_path(icon_id: int, *, config: EffectIconBuildConfig) -> Path:
    return (
        config.cache_dir
        / config.cache_version
        / f"{icon_id}-sprite-z{config.render_zoom}.png"
    )


def effect_icon_png_cache_metadata_path(
    icon_id: int,
    *,
    config: EffectIconBuildConfig,
) -> Path:
    return effect_icon_png_cache_path(icon_id, config=config).with_suffix(".json")


def _cache_matches_asset(
    icon_id: int,
    check: EffectIconAssetCheck,
    *,
    config: EffectIconBuildConfig,
    logger: logging.Logger,
) -> bool:
    metadata_path = effect_icon_png_cache_metadata_path(icon_id, config=config)
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        logger.debug(
            "Effect icon PNG cache metadata is unavailable for %s: %s",
            icon_id,
            _short_error(error),
        )
        return False
    if not isinstance(metadata, dict):
        return False
    cached_length = metadata.get("asset_content_length")
    return isinstance(cached_length, int) and cached_length == check.content_length


def load_effect_icon_png_cache(
    icon_id: int,
    check: EffectIconAssetCheck,
    *,
    config: EffectIconBuildConfig,
    logger: logging.Logger,
) -> bytes | None:
    path = effect_icon_png_cache_path(icon_id, config=config)
    if not path.is_file() or not _cache_matches_asset(
        icon_id,
        check,
        config=config,
        logger=logger,
    ):
        return None
    try:
        data = path.read_bytes()
        visible_png_pixel_count(data, config=config)
    except (OSError, ValueError) as error:
        logger.warning(
            "Ignoring invalid cached effect icon PNG %s: %s",
            path,
            _short_error(error),
        )
        return None
    return data


def save_effect_icon_png_cache(
    icon_id: int,
    data: bytes,
    check: EffectIconAssetCheck,
    *,
    config: EffectIconBuildConfig,
    logger: logging.Logger,
) -> bool:
    try:
        visible_png_pixel_count(data, config=config)
        path = effect_icon_png_cache_path(icon_id, config=config)
        metadata_path = effect_icon_png_cache_metadata_path(icon_id, config=config)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        temp_path = Path(temp_name)
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        temp_path.replace(path)
        metadata_path.write_text(
            json.dumps(
                {
                    "asset_content_length": check.content_length,
                    "icon_id": icon_id,
                    "renderer_version": config.cache_version,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return True
    except (OSError, ValueError) as error:
        logger.warning(
            "Failed to cache effect icon PNG %s: %s",
            icon_id,
            _short_error(error),
        )
        return False


def _render_effect_icon_png(
    icon_id: int,
    check: EffectIconAssetCheck,
    *,
    config: EffectIconBuildConfig,
    download_effect_icon: DownloadEffectIcon,
    logger: logging.Logger,
) -> EffectIconPngRender:
    cached_png = load_effect_icon_png_cache(
        icon_id,
        check,
        config=config,
        logger=logger,
    )
    if cached_png is not None:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=True,
            content_type="image/png",
            content_length=len(cached_png),
            data=cached_png,
            error="",
        )
    if not config.png_render_enabled:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error="PNG rendering disabled",
        )
    if not check.available and check.status != 0:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error=check.error or "SWF asset unavailable",
        )
    try:
        swf_data = download_effect_icon(check)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            swf_path = temp_path / f"{icon_id}.swf"
            swf_path.write_bytes(swf_data)
            try:
                png_data = _render_full_effect_icon_png(
                    swf_path,
                    temp_path,
                    config=config,
                )
            except (
                OSError,
                subprocess.SubprocessError,
                ValueError,
                RuntimeError,
            ) as full_render_error:
                logger.warning(
                    "Full effect icon render failed for %s; falling back to shape export: %s",
                    icon_id,
                    _short_error(full_render_error),
                )
                png_data = _render_shape_effect_icon_png(
                    swf_path,
                    temp_path,
                    config=config,
                )
        save_effect_icon_png_cache(
            icon_id,
            png_data,
            check,
            config=config,
            logger=logger,
        )
        return EffectIconPngRender(
            icon_id=icon_id,
            available=True,
            content_type="image/png",
            content_length=len(png_data),
            data=png_data,
            error="",
        )
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        RuntimeError,
    ) as error:
        return EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type="",
            content_length=None,
            data=None,
            error=_short_error(error),
        )


def render_effect_icon_png_assets(
    checks: dict[int, EffectIconAssetCheck],
    *,
    config: EffectIconBuildConfig,
    download_effect_icon: DownloadEffectIcon,
    logger: logging.Logger,
    require_any: bool = True,
) -> dict[int, EffectIconPngRender]:
    """Render verified SWFs concurrently, with cache validation and fallback."""

    if not checks:
        return {}
    renderable_checks = [
        check for check in checks.values() if check.available or check.status == 0
    ]
    if config.png_render_enabled and renderable_checks:
        if shutil.which(config.java_command) is None:
            raise FileNotFoundError(f"Java command not found: {config.java_command}")
        if not config.ffdec_jar.is_file():
            raise FileNotFoundError(f"FFDec jar not found: {config.ffdec_jar}")
    logger.info("Rendering official effect icon PNGs: %s unique icons", len(checks))
    renders: dict[int, EffectIconPngRender] = {}
    worker_count = min(config.render_workers, len(checks))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _render_effect_icon_png,
                icon_id,
                check,
                config=config,
                download_effect_icon=download_effect_icon,
                logger=logger,
            ): icon_id
            for icon_id, check in sorted(checks.items())
        }
        for completed_count, future in enumerate(as_completed(futures), start=1):
            icon_id = futures[future]
            try:
                renders[icon_id] = future.result()
            except Exception as error:
                renders[icon_id] = EffectIconPngRender(
                    icon_id=icon_id,
                    available=False,
                    content_type="",
                    content_length=None,
                    data=None,
                    error=_short_error(error),
                )
            if completed_count % 20 == 0 or completed_count == len(futures):
                available_count = sum(
                    1 for render in renders.values() if render.available
                )
                logger.info(
                    "Effect icon PNG render progress: %s/%s completed, %s available",
                    completed_count,
                    len(futures),
                    available_count,
                )
    available_count = sum(1 for render in renders.values() if render.available)
    if config.png_require_cached:
        missing_icon_ids = [
            icon_id
            for icon_id, check in checks.items()
            if (check.available or check.status == 0)
            and not renders[icon_id].available
        ]
        if missing_icon_ids:
            preview = ", ".join(str(icon_id) for icon_id in missing_icon_ids[:10])
            raise ValueError(
                "Missing pre-rendered effect icon PNGs: "
                f"{preview}" + (" ..." if len(missing_icon_ids) > 10 else "")
            )
    if config.png_render_enabled and available_count == 0 and require_any:
        first_errors = "; ".join(
            render.error for render in list(renders.values())[:5] if render.error
        )
        raise ValueError(
            "FFDec did not render any visible effect icon PNGs"
            + (f": {first_errors}" if first_errors else "")
        )
    logger.info(
        "Rendered official effect icon PNGs: %s/%s available",
        available_count,
        len(renders),
    )
    return renders
