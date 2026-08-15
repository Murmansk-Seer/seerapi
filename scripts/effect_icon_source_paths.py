# SPDX-License-Identifier: MIT
"""Pure path and identifier rules for official effect icon sources."""

from __future__ import annotations

from urllib.parse import urljoin

if __package__:
    from .effect_icon_build_types import (
        EffectIconBuildConfig,
        UnityEffectIconPngSource,
    )
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconBuildConfig,
        UnityEffectIconPngSource,
    )


def effect_icon_asset_url(icon_id: int, *, config: EffectIconBuildConfig) -> str:
    base_url = config.effect_icon_asset_base_url.rstrip("/") + "/"
    return urljoin(base_url, f"{icon_id}{config.effect_icon_asset_suffix}")


def unity_effect_icon_asset_path(
    icon_id: int,
    *,
    config: EffectIconBuildConfig,
) -> str:
    return f"{config.unity_asset_prefix}{icon_id}{config.unity_asset_suffix}"


def unity_effect_icon_expected_url(
    icon_id: int,
    *,
    config: EffectIconBuildConfig,
) -> str:
    base_url = config.default_package_base_url.rstrip("/")
    return f"{base_url}/#{unity_effect_icon_asset_path(icon_id, config=config)}"


def unity_effect_icon_source_url(source: UnityEffectIconPngSource) -> str:
    return f"{source.bundle_url}#{source.asset_path}"


def unity_effect_icon_id_from_asset_path(
    asset_path: str,
    *,
    config: EffectIconBuildConfig,
) -> int | None:
    if not asset_path.startswith(config.unity_asset_prefix):
        return None
    if not asset_path.endswith(config.unity_asset_suffix):
        return None
    name = asset_path[
        len(config.unity_asset_prefix) : -len(config.unity_asset_suffix)
    ]
    return int(name) if name.isdecimal() else None


def unity_effect_icon_id_from_object_name(name: str) -> int | None:
    normalized = name[:-4] if name.endswith(".png") else name
    return int(normalized) if normalized.isdecimal() else None
