# SPDX-License-Identifier: MIT
"""Pure build-time facts for immutable renderer asset manifests.

This module deliberately has no environment, network, filesystem, CLI, FFDec,
or table-replacement dependency. The release builder owns those adapter and
orchestration concerns; this module only proves whether one SQLite release can
be rendered from one immutable asset-repository snapshot.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import logging
import sqlite3

if __package__:
    from .render_asset_repository import AssetRepositorySnapshot
else:
    from render_asset_repository import (
        AssetRepositorySnapshot,  # type: ignore[import-not-found]
    )


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RenderAssetManifestConfig:
    """Static names and paths that define one published manifest contract."""

    asset_repository_name: str
    manifest_contract_version: str
    manifest_contract_version_key: str
    manifest_revision_key: str
    manifest_scopes_key: str
    manifest_asset_repository_key: str
    manifest_asset_repository_revision_key: str
    pet_info_scope: str
    type_matchup_scope: str
    peak_pool_scope: str
    new_content_standard_scope: str
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
class RemoteRenderAssetRequest:
    """One renderer input resolved from a published repository tree."""

    asset_kind: str
    asset_key: str
    candidate_paths: tuple[str, ...]
    required: bool


@dataclass(frozen=True, slots=True)
class RemoteAssetManifestBuild:
    """Remote inventory facts collected before effect-icon PNG rendering."""

    pet_info_entries: tuple[RenderAssetManifestEntry, ...]
    new_content_standard_entries: tuple[RenderAssetManifestEntry, ...]
    pet_info_scope_complete: bool
    new_content_standard_scope_complete: bool


@dataclass(frozen=True, slots=True)
class RenderAssetManifestBuild:
    """The final release manifest, proven scopes, and consumer metadata."""

    entries: tuple[RenderAssetManifestEntry, ...]
    complete_scopes: tuple[str, ...]
    metadata: dict[str, str]


def collect_remote_asset_manifest(
    conn: sqlite3.Connection,
    snapshot: AssetRepositorySnapshot | None,
    *,
    release_revision: str,
    config: RenderAssetManifestConfig,
) -> RemoteAssetManifestBuild:
    """Collect renderer asset entries and scope proof from published tables."""

    pet_info_entries, pet_info_scope_complete = _build_pet_info_manifest(
        conn,
        snapshot,
        release_revision=release_revision,
        config=config,
    )
    (
        new_content_standard_entries,
        new_content_standard_scope_complete,
    ) = _build_new_content_standard_manifest(
        conn,
        snapshot,
        release_revision=release_revision,
        config=config,
    )
    return RemoteAssetManifestBuild(
        pet_info_entries=pet_info_entries,
        new_content_standard_entries=new_content_standard_entries,
        pet_info_scope_complete=pet_info_scope_complete,
        new_content_standard_scope_complete=new_content_standard_scope_complete,
    )


def build_render_asset_manifest(
    remote: RemoteAssetManifestBuild,
    effect_icon_pngs: Mapping[int, bytes | None],
    snapshot: AssetRepositorySnapshot | None,
    *,
    release_revision: str,
    effect_icon_source_version: str,
    config: RenderAssetManifestConfig,
) -> RenderAssetManifestBuild:
    """Merge remote inventory and generated PNG facts into consumer metadata."""

    entries = (
        *_build_effect_icon_entries(
            effect_icon_pngs,
            release_revision=release_revision,
            effect_icon_source_version=effect_icon_source_version,
        ),
        *remote.pet_info_entries,
        *remote.new_content_standard_entries,
    )
    complete_scopes = complete_render_asset_scopes(
        remote,
        config=config,
    )
    return RenderAssetManifestBuild(
        entries=entries,
        complete_scopes=complete_scopes,
        metadata=render_asset_manifest_metadata(
            entries,
            snapshot,
            complete_scopes=complete_scopes,
            config=config,
        ),
    )


def _build_pet_info_manifest(
    conn: sqlite3.Connection,
    snapshot: AssetRepositorySnapshot | None,
    *,
    release_revision: str,
    config: RenderAssetManifestConfig,
) -> tuple[tuple[RenderAssetManifestEntry, ...], bool]:
    if snapshot is None:
        return (), False
    requests = _pet_info_requests(conn, config=config)
    if requests is None:
        return (), False
    entries, complete = _resolve_requests(
        requests,
        snapshot,
        release_revision=release_revision,
        config=config,
    )
    required_entries = [
        entry
        for entry in entries
        if entry.asset_kind in {'element_type', 'mintmark', 'pet_body', 'pet_head'}
    ]
    return entries, complete and bool(required_entries)


def _build_new_content_standard_manifest(
    conn: sqlite3.Connection,
    snapshot: AssetRepositorySnapshot | None,
    *,
    release_revision: str,
    config: RenderAssetManifestConfig,
) -> tuple[tuple[RenderAssetManifestEntry, ...], bool]:
    if snapshot is None:
        return (), False
    requests = _new_content_standard_requests(conn, config=config)
    if requests is None:
        return (), False
    return _resolve_requests(
        requests,
        snapshot,
        release_revision=release_revision,
        config=config,
    )


def _pet_info_requests(
    conn: sqlite3.Connection,
    *,
    config: RenderAssetManifestConfig,
) -> tuple[RemoteRenderAssetRequest, ...] | None:
    domains = (
        _select_positive_ids(conn, 'pet', 'resource_id'),
        _select_positive_ids(conn, 'element_type', 'id'),
        _select_positive_ids(conn, 'mintmark', 'id'),
        _select_positive_ids(conn, 'item', 'id'),
        _select_positive_ids(conn, config.special_effect_status_table, 'status_id'),
    )
    if any(values is None for values in domains):
        return None
    pet_resource_ids, type_ids, mintmark_ids, item_ids, status_ids = domains
    assert pet_resource_ids is not None
    assert type_ids is not None
    assert mintmark_ids is not None
    assert item_ids is not None
    assert status_ids is not None
    requests: list[RemoteRenderAssetRequest] = []
    for resource_id in pet_resource_ids:
        requests.extend(
            (
                _request(
                    'pet_head',
                    str(resource_id),
                    (f'newseer/assets/art/ui/assets/pet/head/{resource_id}.png',),
                    required=True,
                ),
                _request(
                    'pet_body',
                    str(resource_id),
                    (f'newseer/assets/art/ui/assets/pet/body/{resource_id}.png',),
                    required=True,
                ),
            )
        )
    for type_key in (*map(str, type_ids), 'prop'):
        requests.append(
            _request(
                'element_type',
                type_key,
                (f'newseer/assets/art/ui/assets/pettype/{type_key}.png',),
                required=True,
            )
        )
    for mintmark_id in mintmark_ids:
        requests.append(
            _request(
                'mintmark',
                str(mintmark_id),
                (f'newseer/assets/art/ui/assets/countermark/icon/{mintmark_id}.png',),
                required=True,
            )
        )
    for item_id in item_ids:
        requests.append(
            _request(
                'item',
                str(item_id),
                tuple(
                    f'newseer/assets/art/ui/assets/item/{category}/icon/{item_id}.png'
                    for category in (
                        'doodle',
                        'petitem',
                        'skillstone',
                        'throw',
                        'userinfo',
                    )
                ),
                required=False,
            )
        )
    for status_id in status_ids:
        requests.append(
            _request(
                'sign_buff',
                str(status_id),
                (
                    'newseer/assets/art/ui/assets/battleeffect/signbuff/'
                    f'{status_id}.png',
                ),
                required=False,
            )
        )
    return tuple(sorted(requests, key=lambda item: (item.asset_kind, item.asset_key)))


def _new_content_standard_requests(
    conn: sqlite3.Connection,
    *,
    config: RenderAssetManifestConfig,
) -> tuple[RemoteRenderAssetRequest, ...] | None:
    domains = (
        _select_positive_ids(conn, 'suit', 'id'),
        _select_positive_ids(conn, 'equip', 'id'),
        _select_positive_ids(conn, 'title_part', 'id'),
        _select_positive_ids(conn, 'pet', 'resource_id'),
        _select_positive_ids(
            conn, config.skin_image_resolution_table, 'head_resource_id'
        ),
    )
    if any(values is None for values in domains):
        return None
    suit_ids, equip_ids, title_ids, pet_resource_ids, skin_head_resource_ids = domains
    assert suit_ids is not None
    assert equip_ids is not None
    assert title_ids is not None
    assert pet_resource_ids is not None
    assert skin_head_resource_ids is not None
    requests: list[RemoteRenderAssetRequest] = []
    for suit_id in suit_ids:
        requests.append(
            _request(
                'suit',
                str(suit_id),
                (f'newseer/assets/art/ui/assets/item/cloth/suiticon/{suit_id}.png',),
                required=True,
            )
        )
    for equip_id in equip_ids:
        requests.append(
            _request(
                'equip',
                str(equip_id),
                (f'newseer/assets/art/ui/assets/item/cloth/prev/{equip_id}.png',),
                required=True,
            )
        )
    for title_id in title_ids:
        requests.append(
            _request(
                'title',
                str(title_id),
                (f'newseer/assets/art/ui/assets/achieve/title/{title_id}.png',),
                required=True,
            )
        )
    for resource_id in sorted(set(skin_head_resource_ids).difference(pet_resource_ids)):
        requests.append(
            _request(
                'pet_head',
                str(resource_id),
                (f'newseer/assets/art/ui/assets/pet/head/{resource_id}.png',),
                required=True,
            )
        )
    return tuple(sorted(requests, key=lambda item: (item.asset_kind, item.asset_key)))


def _select_positive_ids(
    conn: sqlite3.Connection,
    table: str,
    column: str,
) -> tuple[int, ...] | None:
    try:
        rows = conn.execute(
            f'SELECT DISTINCT {column} FROM {table} '
            f'WHERE {column} > 0 ORDER BY {column}'
        ).fetchall()
    except sqlite3.OperationalError:
        logger.warning(
            'Render asset inventory cannot read %s.%s; scope stays incomplete',
            table,
            column,
        )
        return None
    return tuple(int(row[0]) for row in rows)


def _request(
    asset_kind: str,
    asset_key: str,
    candidate_paths: tuple[str, ...],
    *,
    required: bool,
) -> RemoteRenderAssetRequest:
    return RemoteRenderAssetRequest(
        asset_kind=asset_kind,
        asset_key=asset_key,
        candidate_paths=candidate_paths,
        required=required,
    )


def _resolve_requests(
    requests: tuple[RemoteRenderAssetRequest, ...],
    snapshot: AssetRepositorySnapshot,
    *,
    release_revision: str,
    config: RenderAssetManifestConfig,
) -> tuple[tuple[RenderAssetManifestEntry, ...], bool]:
    entries: list[RenderAssetManifestEntry] = []
    complete = True
    for request in requests:
        matched_path = next(
            (
                path
                for path in request.candidate_paths
                if path in snapshot.blobs_by_path
            ),
            None,
        )
        available = matched_path is not None
        if request.required and not available:
            complete = False
        source = (
            f'{config.asset_repository_name}@{snapshot.revision}:'
            f'{matched_path}#blob:{snapshot.blobs_by_path[matched_path]}'
            if matched_path is not None
            else f'{config.asset_repository_name}@{snapshot.revision}:missing:'
            + '|'.join(request.candidate_paths)
        )
        entries.append(
            RenderAssetManifestEntry(
                asset_kind=request.asset_kind,
                asset_key=request.asset_key,
                sha256='',
                release_revision=release_revision,
                available=available,
                source=source,
            )
        )
    return tuple(entries), complete


def _build_effect_icon_entries(
    effect_icon_pngs: Mapping[int, bytes | None],
    *,
    release_revision: str,
    effect_icon_source_version: str,
) -> tuple[RenderAssetManifestEntry, ...]:
    return tuple(
        RenderAssetManifestEntry(
            asset_kind='soulmark_icon_png',
            asset_key=str(icon_id),
            sha256=(hashlib.sha256(data).hexdigest() if data is not None else ''),
            release_revision=release_revision,
            available=data is not None,
            source=(f'ConfigPackage/effectIcon.bytes#{effect_icon_source_version}'),
        )
        for icon_id, data in sorted(effect_icon_pngs.items())
    )


def complete_render_asset_scopes(
    remote: RemoteAssetManifestBuild,
    *,
    config: RenderAssetManifestConfig,
) -> tuple[str, ...]:
    """Prove renderer subsets without requiring unrelated pet materials."""

    observed_kinds = {entry.asset_kind for entry in remote.pet_info_entries}
    unavailable_kinds = {
        entry.asset_kind for entry in remote.pet_info_entries if not entry.available
    }
    complete_kinds = observed_kinds - unavailable_kinds
    scopes: list[str] = []
    if remote.pet_info_scope_complete:
        scopes.append(config.pet_info_scope)
    for scope, required_kinds in (
        (config.type_matchup_scope, {'element_type'}),
        (config.peak_pool_scope, {'pet_head', 'element_type'}),
    ):
        if required_kinds <= complete_kinds:
            scopes.append(scope)
    if remote.pet_info_scope_complete and remote.new_content_standard_scope_complete:
        scopes.append(config.new_content_standard_scope)
    return tuple(scopes)


def render_asset_manifest_metadata(
    entries: tuple[RenderAssetManifestEntry, ...],
    snapshot: AssetRepositorySnapshot | None,
    *,
    complete_scopes: tuple[str, ...],
    config: RenderAssetManifestConfig,
) -> dict[str, str]:
    return {
        config.manifest_revision_key: render_asset_manifest_revision(entries),
        config.manifest_contract_version_key: config.manifest_contract_version,
        config.manifest_scopes_key: json.dumps(complete_scopes, separators=(',', ':')),
        config.manifest_asset_repository_key: (
            config.asset_repository_name if snapshot is not None else ''
        ),
        config.manifest_asset_repository_revision_key: (
            snapshot.revision if snapshot is not None else ''
        ),
        'render_asset_manifest_count': str(len(entries)),
        'render_asset_manifest_available_count': str(
            sum(1 for entry in entries if entry.available)
        ),
    }


def render_asset_manifest_revision(
    entries: tuple[RenderAssetManifestEntry, ...],
) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: (item.asset_kind, item.asset_key)):
        digest.update(entry.asset_kind.encode('utf-8'))
        digest.update(b'\0')
        digest.update(entry.asset_key.encode('utf-8'))
        digest.update(b'\0')
        digest.update(entry.sha256.encode('ascii'))
        digest.update(b'\0')
        digest.update(entry.release_revision.encode('utf-8'))
        digest.update(b'\0')
        digest.update(entry.source.encode('utf-8'))
        digest.update(b'\0')
        digest.update(b'1' if entry.available else b'0')
        digest.update(b'\n')
    return digest.hexdigest()
