# SPDX-License-Identifier: MIT
"""Shared value objects for build-time effect icon PNG publication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class UnityBundleDescriptor(Protocol):
    """The narrow bundle fact required by effect-icon source selection."""

    file_size: int


@dataclass(frozen=True, slots=True)
class EffectIconBuildConfig:
    """Fully resolved build settings shared by source and PNG adapters."""

    unity_asset_prefix: str
    unity_asset_suffix: str
    unity_png_enabled: bool
    default_package_base_url: str
    default_package_name: str
    effect_icon_asset_base_url: str
    effect_icon_asset_suffix: str
    asset_verify_timeout_seconds: float
    asset_verify_workers: int
    prefer_flash: bool
    png_render_enabled: bool
    png_require_cached: bool
    java_command: str
    ffdec_jar: Path
    render_zoom: int
    render_timeout_seconds: float
    composite_render_timeout_seconds: float
    shape_render_timeout_seconds: float
    render_workers: int
    cache_version: str
    cache_dir: Path
    max_png_dimension: int


@dataclass(frozen=True, slots=True)
class UnityEffectIconPngSource:
    icon_id: int
    asset_path: str
    bundle: UnityBundleDescriptor
    bundle_url: str


@dataclass(frozen=True, slots=True)
class EffectIconAssetCheck:
    icon_id: int
    url: str
    available: bool
    status: int
    content_type: str
    content_length: int | None
    error: str


@dataclass(frozen=True, slots=True)
class EffectIconPngRender:
    icon_id: int
    available: bool
    content_type: str
    content_length: int | None
    data: bytes | None
    error: str


@dataclass(frozen=True, slots=True)
class UnityEffectIconPngLoad:
    package_version: str
    total_manifest_icon_count: int
    sources: dict[int, UnityEffectIconPngSource]
    asset_checks: dict[int, EffectIconAssetCheck]
    png_renders: dict[int, EffectIconPngRender]


@dataclass(frozen=True, slots=True)
class EffectIconPngResolution:
    asset_checks: dict[int, EffectIconAssetCheck]
    png_renders: dict[int, EffectIconPngRender]
    preferred_source: str
    unity_package_version: str
    unity_manifest_icon_count: int
    unity_png_available_count: int
    unity_missing_icon_ids: tuple[int, ...]
    flash_png_available_count: int
    flash_missing_icon_ids: tuple[int, ...]
    unity_fallback_icon_count: int
    swf_fallback_icon_count: int


@dataclass(frozen=True, slots=True)
class SoulmarkIconRenderIssue:
    icon_id: int
    soulmark_id: int
    pet_id: int
    pet_name: str
    effect_id: int
    icon_asset_status: int
    icon_asset_error: str
    icon_png_error: str
