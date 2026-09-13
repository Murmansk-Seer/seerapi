# SPDX-License-Identifier: MIT
"""Seal render assets after generated PNG publication."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time

if __package__:
    from . import build_seerapi_data_db as builder
    from .release_render_manifest_tables import replace_render_asset_manifest_table
    from .render_asset_manifest_build import (
        build_render_asset_manifest,
        collect_remote_asset_manifest,
    )
    from .render_asset_repository import AssetRepositorySnapshot
else:
    import build_seerapi_data_db as builder  # type: ignore[import-not-found]
    from release_render_manifest_tables import (  # type: ignore[import-not-found]
        replace_render_asset_manifest_table,
    )
    from render_asset_manifest_build import (  # type: ignore[import-not-found]
        build_render_asset_manifest,
        collect_remote_asset_manifest,
    )
    from render_asset_repository import (  # type: ignore[import-not-found]
        AssetRepositorySnapshot,
    )

_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_LEGACY_REPOSITORY_KEYS = (
    "render_asset_manifest_asset_repository",
    "render_asset_manifest_asset_repository_revision",
)


def _generated_snapshot(
    directory: Path,
    *,
    repository: str,
    revision: str,
) -> AssetRepositorySnapshot:
    if not _COMMIT_PATTERN.fullmatch(revision):
        raise ValueError("generated asset revision must be a full Git commit SHA")
    paths = tuple(sorted(directory.glob("*.png")))
    sha256_by_path = {
        path.relative_to(directory.parent).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in paths
    }
    return AssetRepositorySnapshot(
        repository=repository,
        revision=revision,
        blobs_by_path=dict(sha256_by_path),
        sha256_by_path=sha256_by_path,
    )


def _published_default_snapshot(
    connection: sqlite3.Connection,
    metadata: dict[str, str],
) -> AssetRepositorySnapshot:
    repositories = json.loads(metadata[builder.RENDER_ASSET_MANIFEST_REPOSITORIES_KEY])
    source = repositories["default"]
    repository = str(source["repository"])
    revision = str(source["revision"])
    prefix = f"{repository}@{revision}:"
    blobs: dict[str, str] = {}
    for raw_source, in connection.execute(
        "SELECT source FROM render_asset_manifest WHERE available = 1"
    ):
        value = str(raw_source)
        if not value.startswith(prefix) or "#blob:" not in value:
            continue
        path, blob = value[len(prefix) :].split("#blob:", 1)
        blobs[path] = blob
    if not blobs:
        raise ValueError("published default render asset snapshot is empty")
    return AssetRepositorySnapshot(
        repository=repository,
        revision=revision,
        blobs_by_path=blobs,
    )


def finalize_manifest(
    database: Path,
    *,
    mount_directory: Path,
    mount_repository: str,
    mount_revision: str,
) -> None:
    with sqlite3.connect(database) as connection:
        metadata = dict(
            connection.execute("SELECT key, value FROM ironsbot_metadata")
        )
        snapshots = {
            "default": _published_default_snapshot(connection, metadata),
            "mount": _generated_snapshot(
                mount_directory,
                repository=mount_repository,
                revision=mount_revision,
            ),
        }
        release_revision = metadata["config_package_version"]
        icon_source_version = metadata["effect_icon_png_cache_version"]
        icon_pngs = {
            int(icon_id): bytes(png_data)
            for icon_id, png_data in connection.execute(
                "SELECT DISTINCT icon_id, icon_png FROM soulmark_icon "
                "WHERE icon_png_available = 1 AND icon_png IS NOT NULL"
            )
        }
        remote = collect_remote_asset_manifest(
            connection,
            snapshots,
            release_revision=release_revision,
            config=builder.RENDER_ASSET_MANIFEST_CONFIG,
        )
        manifest = build_render_asset_manifest(
            remote,
            icon_pngs,
            snapshots,
            release_revision=release_revision,
            effect_icon_source_version=icon_source_version,
            config=builder.RENDER_ASSET_MANIFEST_CONFIG,
        )
        replace_render_asset_manifest_table(
            connection,
            manifest.entries,
            updated_at=time.time(),
        )
        connection.executemany(
            "INSERT INTO ironsbot_metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            sorted(manifest.metadata.items()),
        )
        connection.executemany(
            "DELETE FROM ironsbot_metadata WHERE key = ?",
            ((key,) for key in _LEGACY_REPOSITORY_KEYS),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--mount-directory", type=Path, required=True)
    parser.add_argument("--mount-repository", required=True)
    parser.add_argument("--mount-revision", required=True)
    args = parser.parse_args()
    finalize_manifest(
        args.database,
        mount_directory=args.mount_directory,
        mount_repository=args.mount_repository,
        mount_revision=args.mount_revision,
    )


if __name__ == "__main__":
    main()
