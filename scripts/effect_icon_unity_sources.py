# SPDX-License-Identifier: MIT
"""Unity DefaultPackage adapter for build-time effect icon PNG sources.

The adapter receives network and manifest functions from the build entrypoint.
It owns only Unity bundle discovery and extraction, keeping the orchestrator
free of UnityPy and package-layout details.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import io
import logging
from typing import BinaryIO, Protocol
from urllib.parse import urljoin

if __package__:
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
        UnityBundleDescriptor,
        UnityEffectIconPngLoad,
        UnityEffectIconPngSource,
    )
    from .effect_icon_png_renderer import visible_png_pixel_count
    from .effect_icon_source_paths import (
        unity_effect_icon_expected_url,
        unity_effect_icon_id_from_asset_path,
        unity_effect_icon_id_from_object_name,
        unity_effect_icon_source_url,
    )
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconBuildConfig,
        EffectIconPngRender,
        UnityBundleDescriptor,
        UnityEffectIconPngLoad,
        UnityEffectIconPngSource,
    )
    from effect_icon_png_renderer import (  # type: ignore[import-not-found]
        visible_png_pixel_count,
    )
    from effect_icon_source_paths import (  # type: ignore[import-not-found]
        unity_effect_icon_expected_url,
        unity_effect_icon_id_from_asset_path,
        unity_effect_icon_id_from_object_name,
        unity_effect_icon_source_url,
    )


class UnityPackageManifest(Protocol):
    """The package facts needed to locate DefaultPackage icon bundles."""

    @property
    def assets(self) -> Mapping[str, 'UnityBundleDescriptor']: ...


class EncodableImage(Protocol):
    def convert(self, mode: str) -> 'EncodableImage': ...

    def save(self, output: BinaryIO, *, format: str) -> None: ...


FetchPackageManifest = Callable[[str, str], tuple[str, UnityPackageManifest]]
DownloadBytes = Callable[[str], bytes]


def _short_error(error: Exception | str) -> str:
    return str(error).replace('\n', ' ')[:200]


def _encode_unity_image_png(
    image: EncodableImage | None, *, config: EffectIconBuildConfig
) -> bytes:
    if image is None:
        raise ValueError('Unity object has no image data')
    image = image.convert('RGBA')
    output = io.BytesIO()
    image.save(output, format='PNG')
    png_data = output.getvalue()
    visible_png_pixel_count(png_data, config=config)
    return png_data


def extract_unity_effect_icon_pngs(
    bundle_data: bytes,
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
) -> tuple[dict[int, bytes], dict[int, str]]:
    """Extract the preferred visible Sprite or Texture2D image for each icon."""

    import UnityPy

    candidates: dict[int, tuple[int, bytes]] = {}
    errors: dict[int, str] = {}
    env = UnityPy.load(io.BytesIO(bundle_data))
    for obj in env.objects:
        object_type = obj.type.name
        if object_type not in {'Sprite', 'Texture2D'}:
            continue
        icon_id: int | None = None
        try:
            data = obj.read()
            icon_id = unity_effect_icon_id_from_object_name(str(data.m_Name))
            if icon_id is None or icon_id not in icon_ids:
                continue
            png_data = _encode_unity_image_png(data.image, config=config)
        except Exception as error:
            if icon_id is not None:
                errors[icon_id] = _short_error(error)
            continue
        priority = 0 if object_type == 'Sprite' else 1
        existing = candidates.get(icon_id)
        if existing is None or priority < existing[0]:
            candidates[icon_id] = (priority, png_data)
    return ({icon_id: png for icon_id, (_, png) in candidates.items()}, errors)


def missing_unity_effect_icon_png_load(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    error: str,
    status: int = 0,
) -> UnityEffectIconPngLoad:
    return UnityEffectIconPngLoad(
        package_version='',
        total_manifest_icon_count=0,
        sources={},
        asset_checks={
            icon_id: EffectIconAssetCheck(
                icon_id=icon_id,
                url=unity_effect_icon_expected_url(icon_id, config=config),
                available=False,
                status=status,
                content_type='',
                content_length=None,
                error=error,
            )
            for icon_id in icon_ids
        },
        png_renders={
            icon_id: EffectIconPngRender(
                icon_id=icon_id,
                available=False,
                content_type='',
                content_length=None,
                data=None,
                error=error,
            )
            for icon_id in icon_ids
        },
    )


def fetch_unity_effect_icon_png_sources(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    fetch_package_manifest: FetchPackageManifest,
) -> tuple[str, int, dict[int, UnityEffectIconPngSource]]:
    base_url = config.default_package_base_url.rstrip('/') + '/'
    version, manifest = fetch_package_manifest(base_url, config.default_package_name)
    all_sources: dict[int, UnityEffectIconPngSource] = {}
    for asset_path, bundle in manifest.assets.items():
        icon_id = unity_effect_icon_id_from_asset_path(asset_path, config=config)
        if icon_id is None:
            continue
        all_sources[icon_id] = UnityEffectIconPngSource(
            icon_id=icon_id,
            asset_path=asset_path,
            bundle=bundle,
            bundle_url=urljoin(base_url, bundle.file_hash),
        )
    return (
        version,
        len(all_sources),
        {icon_id: all_sources[icon_id] for icon_id in icon_ids & all_sources.keys()},
    )


def load_unity_effect_icon_png_assets(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    fetch_package_manifest: FetchPackageManifest,
    download_bytes: DownloadBytes,
) -> UnityEffectIconPngLoad:
    if not icon_ids:
        return missing_unity_effect_icon_png_load(icon_ids, config=config, error='')
    if not config.unity_png_enabled:
        return missing_unity_effect_icon_png_load(
            icon_ids,
            config=config,
            error='Unity effect icon PNG loading disabled',
        )

    package_version, total_icon_count, sources = fetch_unity_effect_icon_png_sources(
        icon_ids,
        config=config,
        fetch_package_manifest=fetch_package_manifest,
    )
    asset_checks: dict[int, EffectIconAssetCheck] = {}
    png_renders: dict[int, EffectIconPngRender] = {}
    missing_error = 'Unity DefaultPackage effectIcon PNG missing'
    for icon_id in icon_ids - sources.keys():
        asset_checks[icon_id] = EffectIconAssetCheck(
            icon_id=icon_id,
            url=unity_effect_icon_expected_url(icon_id, config=config),
            available=False,
            status=404,
            content_type='',
            content_length=None,
            error=missing_error,
        )
        png_renders[icon_id] = EffectIconPngRender(
            icon_id=icon_id,
            available=False,
            content_type='',
            content_length=None,
            data=None,
            error=missing_error,
        )

    sources_by_bundle_url: dict[str, list[UnityEffectIconPngSource]] = {}
    for source in sources.values():
        sources_by_bundle_url.setdefault(source.bundle_url, []).append(source)

    for bundle_url, bundle_sources in sources_by_bundle_url.items():
        source_icon_ids = {source.icon_id for source in bundle_sources}
        try:
            pngs, extraction_errors = extract_unity_effect_icon_pngs(
                download_bytes(bundle_url), source_icon_ids, config=config
            )
        except Exception as error:
            pngs = {}
            extraction_errors = {
                icon_id: _short_error(error) for icon_id in source_icon_ids
            }
        for source in bundle_sources:
            png_data = pngs.get(source.icon_id)
            source_url = unity_effect_icon_source_url(source)
            if png_data is None:
                error = extraction_errors.get(
                    source.icon_id, 'Unity bundle did not contain a visible PNG'
                )
                asset_checks[source.icon_id] = EffectIconAssetCheck(
                    icon_id=source.icon_id,
                    url=source_url,
                    available=True,
                    status=200,
                    content_type='application/octet-stream',
                    content_length=source.bundle.file_size,
                    error='',
                )
                png_renders[source.icon_id] = EffectIconPngRender(
                    icon_id=source.icon_id,
                    available=False,
                    content_type='',
                    content_length=None,
                    data=None,
                    error=error,
                )
                continue
            asset_checks[source.icon_id] = EffectIconAssetCheck(
                icon_id=source.icon_id,
                url=source_url,
                available=True,
                status=200,
                content_type='image/png',
                content_length=len(png_data),
                error='',
            )
            png_renders[source.icon_id] = EffectIconPngRender(
                icon_id=source.icon_id,
                available=True,
                content_type='image/png',
                content_length=len(png_data),
                data=png_data,
                error='',
            )

    return UnityEffectIconPngLoad(
        package_version=package_version,
        total_manifest_icon_count=total_icon_count,
        sources=sources,
        asset_checks=asset_checks,
        png_renders=png_renders,
    )


def unity_effect_icon_swf_fallback_icon_ids(
    icon_ids: set[int],
    *,
    config: EffectIconBuildConfig,
    fetch_package_manifest: FetchPackageManifest,
    logger: logging.Logger,
) -> list[int]:
    if not icon_ids or config.prefer_flash or not config.unity_png_enabled:
        return sorted(icon_ids)
    try:
        _, _, sources = fetch_unity_effect_icon_png_sources(
            icon_ids,
            config=config,
            fetch_package_manifest=fetch_package_manifest,
        )
    except (OSError, TimeoutError, ValueError) as error:
        logger.warning(
            'Unity effect icon manifest lookup skipped; rendering SWF fallback: %s',
            _short_error(error),
        )
        return sorted(icon_ids)
    return sorted(icon_ids - sources.keys())
