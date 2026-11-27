# SPDX-License-Identifier: MIT
"""Immutable data types for the release-owned renderer asset manifest."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderAssetManifestConfig:
    """Static names and paths that define one published manifest contract."""

    manifest_contract_version: str
    manifest_contract_version_key: str
    manifest_revision_key: str
    manifest_scopes_key: str
    manifest_repositories_key: str
    pet_info_scope: str
    type_matchup_scope: str
    peak_pool_scope: str
    new_content_standard_scope: str
    skin_body_scope: str
    special_effect_status_table: str
    skin_image_resolution_table: str


@dataclass(frozen=True, slots=True)
class RenderAssetManifestEntry:
    """One release-owned material fact used to invalidate final render caches."""

    asset_kind: str
    asset_key: str
    sha256: str
    release_revision: str
    available: bool
    source: str


@dataclass(frozen=True, slots=True)
class RemoteRenderAssetCandidate:
    """One immutable repository/path candidate, in lookup order."""

    repository_kind: str
    path: str


@dataclass(frozen=True, slots=True)
class RemoteRenderAssetRequest:
    """One renderer input resolved from a published repository tree."""

    asset_kind: str
    asset_key: str
    candidates: tuple[RemoteRenderAssetCandidate, ...]
    required: bool


@dataclass(frozen=True, slots=True)
class RemoteAssetManifestBuild:
    """Remote inventory facts collected before effect-icon PNG rendering."""

    pet_info_entries: tuple[RenderAssetManifestEntry, ...]
    new_content_standard_entries: tuple[RenderAssetManifestEntry, ...]
    pet_info_scope_complete: bool
    new_content_standard_scope_complete: bool
    skin_body_entries: tuple[RenderAssetManifestEntry, ...]
    skin_body_scope_complete: bool
    supplemental_entries: tuple[RenderAssetManifestEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderAssetManifestBuild:
    """The final release manifest, proven scopes, and consumer metadata."""

    entries: tuple[RenderAssetManifestEntry, ...]
    complete_scopes: tuple[str, ...]
    metadata: dict[str, str]
