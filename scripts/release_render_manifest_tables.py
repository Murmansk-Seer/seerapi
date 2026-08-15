# SPDX-License-Identifier: MIT
"""SQLite writer for published render-asset manifest facts."""

from __future__ import annotations

import sqlite3

if __package__:
    from .render_asset_manifest_build import RenderAssetManifestEntry
else:
    from render_asset_manifest_build import (  # type: ignore[import-not-found]
        RenderAssetManifestEntry,
    )


RENDER_ASSET_MANIFEST_TABLE = "render_asset_manifest"


def replace_render_asset_manifest_table(
    conn: sqlite3.Connection,
    entries: tuple[RenderAssetManifestEntry, ...],
    *,
    updated_at: float,
) -> None:
    """Replace release-owned render material facts atomically with the build."""
    conn.execute(f"DROP TABLE IF EXISTS {RENDER_ASSET_MANIFEST_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {RENDER_ASSET_MANIFEST_TABLE} (
            asset_kind TEXT NOT NULL,
            asset_key TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            release_revision TEXT NOT NULL,
            available INTEGER NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (asset_kind, asset_key)
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {RENDER_ASSET_MANIFEST_TABLE}
            (
                asset_kind,
                asset_key,
                sha256,
                release_revision,
                available,
                source,
                updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                entry.asset_kind,
                entry.asset_key,
                entry.sha256,
                entry.release_revision,
                int(entry.available),
                entry.source,
                updated_at,
            )
            for entry in entries
        ],
    )
