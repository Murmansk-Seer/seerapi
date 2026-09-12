# SPDX-License-Identifier: MIT
"""Coordinate Flash and Unity effect-icon sources into publishable PNG facts."""

from __future__ import annotations

from dataclasses import replace
from functools import partial
import logging
from urllib.error import HTTPError, URLError

if __package__:
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
        EffectIconPngResolution,
        UnityEffectIconPngLoad,
    )
    from .effect_icon_flash_sources import (
        BuildRequest,
        OpenUrl,
        download_effect_icon_asset,
        verify_effect_icon_assets,
    )
    from .effect_icon_png_renderer import render_effect_icon_png_assets
    from .effect_icon_source_paths import effect_icon_asset_url
    from .effect_icon_unity_sources import (
        DownloadBytes,
        FetchPackageManifest,
        load_unity_effect_icon_png_assets,
        missing_unity_effect_icon_png_load,
    )
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
        EffectIconPngResolution,
        UnityEffectIconPngLoad,
    )
    from effect_icon_flash_sources import (  # type: ignore[import-not-found]
        BuildRequest,
        OpenUrl,
        download_effect_icon_asset,
        verify_effect_icon_assets,
    )
    from effect_icon_png_renderer import (  # type: ignore[import-not-found]
        render_effect_icon_png_assets,
    )
    from effect_icon_source_paths import (  # type: ignore[import-not-found]
        effect_icon_asset_url,
    )
    from effect_icon_unity_sources import (  # type: ignore[import-not-found]
        DownloadBytes,
        FetchPackageManifest,
        load_unity_effect_icon_png_assets,
        missing_unity_effect_icon_png_load,
    )


def _short_error(error: Exception | str) -> str:
    return str(error).replace("\n", " ")[:200]


def load_flash_effect_icon_png_assets(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    request: BuildRequest,
    open_url: OpenUrl,
    logger: logging.Logger,
    require_any: bool,
) -> tuple[dict[int, EffectIconAssetCheck], dict[int, EffectIconPngRender]]:
    """Verify and render Flash icons through the same path used by fallback shards."""

    if not icon_ids:
        return {}, {}
    checks = verify_effect_icon_assets(
        icon_ids,
        config=config,
        request=request,
        open_url=open_url,
        logger=logger,
        require_any=require_any,
    )
    renders = render_effect_icon_png_assets(
        checks,
        config=config,
        download_effect_icon=partial(
            download_effect_icon_asset,
            config=config,
            request=request,
            open_url=open_url,
        ),
        logger=logger,
        require_any=require_any,
    )
    return checks, renders


def _missing_flash_effect_icon_png_assets(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    error: str,
) -> tuple[dict[int, EffectIconAssetCheck], dict[int, EffectIconPngRender]]:
    return (
        {
            icon_id: EffectIconAssetCheck(
                icon_id=icon_id,
                url=effect_icon_asset_url(icon_id, config=config),
                available=False,
                status=0,
                content_type="",
                content_length=None,
                error=error,
            )
            for icon_id in icon_ids
        },
        {
            icon_id: EffectIconPngRender(
                icon_id=icon_id,
                available=False,
                content_type="",
                content_length=None,
                data=None,
                error=error,
            )
            for icon_id in icon_ids
        },
    )


def _empty_resolution(*, prefer_flash: bool) -> EffectIconPngResolution:
    return EffectIconPngResolution(
        asset_checks={},
        png_renders={},
        preferred_source="flash" if prefer_flash else "unity",
        unity_package_version="",
        unity_manifest_icon_count=0,
        unity_png_available_count=0,
        unity_missing_icon_ids=(),
        flash_png_available_count=0,
        flash_missing_icon_ids=(),
        unity_fallback_icon_count=0,
        swf_fallback_icon_count=0,
    )


def _load_unity_or_missing(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    fetch_package_manifest: FetchPackageManifest,
    download_bytes: DownloadBytes,
    logger: logging.Logger,
    failure_label: str,
) -> UnityEffectIconPngLoad:
    try:
        return load_unity_effect_icon_png_assets(
            icon_ids,
            config=config,
            fetch_package_manifest=fetch_package_manifest,
            download_bytes=download_bytes,
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        logger.warning("%s: %s", failure_label, _short_error(error))
        return missing_unity_effect_icon_png_load(
            icon_ids,
            config=config,
            error=f"Unity effect icon PNG loading failed: {_short_error(error)}",
        )


def resolve_effect_icon_png_assets(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    fetch_package_manifest: FetchPackageManifest,
    download_bytes: DownloadBytes,
    request: BuildRequest,
    open_url: OpenUrl,
    logger: logging.Logger,
) -> EffectIconPngResolution:
    """Apply the configured source preference and per-icon fallback policy."""

    if not icon_ids:
        return _empty_resolution(prefer_flash=config.prefer_flash)

    # Per-source misses are resolved by fallback; enforce completeness only on
    # the combined result, without discarding successful cached PNGs.
    source_config = replace(config, png_require_cached=False)

    if config.prefer_flash:
        try:
            flash_checks, flash_renders = load_flash_effect_icon_png_assets(
                icon_ids,
                config=source_config,
                request=request,
                open_url=open_url,
                logger=logger,
                require_any=False,
            )
        except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
            logger.warning(
                "Flash effect icon PNG loading skipped; falling back to Unity PNGs: %s",
                _short_error(error),
            )
            flash_checks, flash_renders = _missing_flash_effect_icon_png_assets(
                icon_ids,
                config=config,
                error=f"Flash effect icon PNG loading failed: {_short_error(error)}",
            )
        flash_missing_ids = {
            icon_id for icon_id in icon_ids if not flash_renders[icon_id].available
        }
        unity_load = _load_unity_or_missing(
            flash_missing_ids,
            config=config,
            fetch_package_manifest=fetch_package_manifest,
            download_bytes=download_bytes,
            logger=logger,
            failure_label="Unity effect icon PNG fallback skipped",
        )
        asset_checks: dict[int, EffectIconAssetCheck] = {}
        png_renders: dict[int, EffectIconPngRender] = {}
        for icon_id in icon_ids:
            flash_render = flash_renders[icon_id]
            unity_render = unity_load.png_renders.get(icon_id)
            if flash_render.available or unity_render is None or not unity_render.available:
                asset_checks[icon_id] = flash_checks[icon_id]
                png_renders[icon_id] = flash_render
            else:
                asset_checks[icon_id] = unity_load.asset_checks[icon_id]
                png_renders[icon_id] = unity_render
        unity_available_ids = {
            icon_id
            for icon_id in flash_missing_ids
            if unity_load.png_renders[icon_id].available
        }
        resolution = EffectIconPngResolution(
            asset_checks=asset_checks,
            png_renders=png_renders,
            preferred_source="flash",
            unity_package_version=unity_load.package_version,
            unity_manifest_icon_count=unity_load.total_manifest_icon_count,
            unity_png_available_count=len(unity_available_ids),
            unity_missing_icon_ids=tuple(sorted(flash_missing_ids - unity_available_ids)),
            flash_png_available_count=sum(
                render.available for render in flash_renders.values()
            ),
            flash_missing_icon_ids=tuple(sorted(flash_missing_ids)),
            unity_fallback_icon_count=len(unity_available_ids),
            swf_fallback_icon_count=0,
        )
        return _validate_resolution(resolution, config=config)

    unity_load = _load_unity_or_missing(
        icon_ids,
        config=config,
        fetch_package_manifest=fetch_package_manifest,
        download_bytes=download_bytes,
        logger=logger,
        failure_label="Unity effect icon PNG loading skipped; falling back to SWF assets",
    )
    unity_missing_ids = {
        icon_id for icon_id in icon_ids if not unity_load.png_renders[icon_id].available
    }
    if unity_missing_ids:
        flash_checks, flash_renders = load_flash_effect_icon_png_assets(
            unity_missing_ids,
            config=source_config,
            request=request,
            open_url=open_url,
            logger=logger,
            require_any=False,
        )
    else:
        flash_checks, flash_renders = {}, {}
    flash_missing_ids = {
        icon_id for icon_id in unity_missing_ids if not flash_renders[icon_id].available
    }
    asset_checks = {}
    png_renders = {}
    for icon_id in icon_ids:
        unity_render = unity_load.png_renders[icon_id]
        flash_render = flash_renders.get(icon_id)
        if unity_render.available or flash_render is None:
            asset_checks[icon_id] = unity_load.asset_checks[icon_id]
            png_renders[icon_id] = unity_render
        else:
            asset_checks[icon_id] = flash_checks[icon_id]
            png_renders[icon_id] = flash_render
    resolution = EffectIconPngResolution(
        asset_checks=asset_checks,
        png_renders=png_renders,
        preferred_source="unity",
        unity_package_version=unity_load.package_version,
        unity_manifest_icon_count=unity_load.total_manifest_icon_count,
        unity_png_available_count=sum(
            render.available for render in unity_load.png_renders.values()
        ),
        unity_missing_icon_ids=tuple(sorted(unity_missing_ids)),
        flash_png_available_count=sum(render.available for render in flash_renders.values()),
        flash_missing_icon_ids=tuple(sorted(flash_missing_ids)),
        unity_fallback_icon_count=0,
        swf_fallback_icon_count=len(unity_missing_ids),
    )
    return _validate_resolution(resolution, config=config)


def _validate_resolution(
    resolution: EffectIconPngResolution, *, config: EffectIconBuildConfig
) -> EffectIconPngResolution:
    if config.png_require_cached:
        missing = sorted(
            icon_id for icon_id, check in resolution.asset_checks.items()
            if (check.available or check.status == 0)
            and not resolution.png_renders[icon_id].available
        )
        if missing:
            preview = ", ".join(map(str, missing[:10]))
            raise ValueError(
                "Missing resolved effect icon PNGs: " + preview
                + (" ..." if len(missing) > 10 else "")
            )
    return resolution
