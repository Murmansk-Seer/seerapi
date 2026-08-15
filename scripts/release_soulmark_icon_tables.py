# SPDX-License-Identifier: MIT
"""SQLite writer for build-time soulmark icon facts and diagnostics."""

from __future__ import annotations

from collections.abc import Iterable
import sqlite3

if __package__:
    from .effect_icon_build_types import (
        EffectIconAssetCheck,
        EffectIconPngRender,
        SoulmarkIconRenderIssue,
    )
else:
    from effect_icon_build_types import (  # type: ignore[import-not-found]
        EffectIconAssetCheck,
        EffectIconPngRender,
        SoulmarkIconRenderIssue,
    )


SOULMARK_ICON_TABLE = "soulmark_icon"
SOULMARK_ICON_RENDER_ISSUE_TABLE = "soulmark_icon_render_issue"


def replace_soulmark_icon_tables(
    conn: sqlite3.Connection,
    *,
    soulmark_icons: Iterable[tuple[int, int, int, int]],
    asset_checks: dict[int, EffectIconAssetCheck],
    png_renders: dict[int, EffectIconPngRender],
    render_issues: Iterable[SoulmarkIconRenderIssue],
    now: float,
) -> None:
    """Replace release-owned icon rows and failed-render diagnostics."""
    icon_rows = [
        (
            soulmark_id,
            pet_id,
            effect_id,
            icon_id,
            effect_icon_runtime_asset_url(asset_checks[icon_id]),
            int(asset_checks[icon_id].available),
            asset_checks[icon_id].status,
            asset_checks[icon_id].content_type,
            asset_checks[icon_id].content_length,
            asset_checks[icon_id].error,
            png_renders[icon_id].data,
            int(png_renders[icon_id].available),
            png_renders[icon_id].content_type,
            png_renders[icon_id].content_length,
            png_renders[icon_id].error,
            "ConfigPackage/effectIcon.bytes",
            now,
        )
        for soulmark_id, pet_id, effect_id, icon_id in soulmark_icons
    ]
    conn.execute(f"DROP TABLE IF EXISTS {SOULMARK_ICON_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SOULMARK_ICON_TABLE} (
            soulmark_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            effect_id INTEGER NOT NULL,
            icon_id INTEGER NOT NULL,
            icon_asset_url TEXT,
            icon_asset_available INTEGER NOT NULL,
            icon_asset_status INTEGER NOT NULL,
            icon_asset_content_type TEXT NOT NULL,
            icon_asset_content_length INTEGER,
            icon_asset_error TEXT NOT NULL,
            icon_png BLOB,
            icon_png_available INTEGER NOT NULL,
            icon_png_content_type TEXT NOT NULL,
            icon_png_content_length INTEGER,
            icon_png_error TEXT NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (soulmark_id, pet_id, effect_id, icon_id)
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {SOULMARK_ICON_TABLE}
            (
                soulmark_id, pet_id, effect_id, icon_id, icon_asset_url,
                icon_asset_available, icon_asset_status, icon_asset_content_type,
                icon_asset_content_length, icon_asset_error, icon_png,
                icon_png_available, icon_png_content_type, icon_png_content_length,
                icon_png_error, source, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        icon_rows,
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{SOULMARK_ICON_TABLE}_soulmark_id
        ON {SOULMARK_ICON_TABLE} (soulmark_id)
        """
    )
    conn.execute(f"DROP TABLE IF EXISTS {SOULMARK_ICON_RENDER_ISSUE_TABLE}")
    conn.execute(
        f"""
        CREATE TABLE {SOULMARK_ICON_RENDER_ISSUE_TABLE} (
            icon_id INTEGER NOT NULL,
            soulmark_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            pet_name TEXT NOT NULL,
            effect_id INTEGER NOT NULL,
            icon_asset_status INTEGER NOT NULL,
            icon_asset_error TEXT NOT NULL,
            icon_png_error TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (icon_id, soulmark_id, pet_id, effect_id)
        )
        """
    )
    conn.executemany(
        f"""
        INSERT INTO {SOULMARK_ICON_RENDER_ISSUE_TABLE}
            (
                icon_id, soulmark_id, pet_id, pet_name, effect_id,
                icon_asset_status, icon_asset_error, icon_png_error, updated_at
            )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                issue.icon_id,
                issue.soulmark_id,
                issue.pet_id,
                issue.pet_name,
                issue.effect_id,
                issue.icon_asset_status,
                issue.icon_asset_error,
                issue.icon_png_error,
                now,
            )
            for issue in render_issues
        ],
    )
    conn.execute(
        f"""
        CREATE INDEX idx_{SOULMARK_ICON_RENDER_ISSUE_TABLE}_pet_id
        ON {SOULMARK_ICON_RENDER_ISSUE_TABLE} (pet_id)
        """
    )


def effect_icon_runtime_asset_url(check: EffectIconAssetCheck) -> str | None:
    """Keep retryable icon URLs while omitting confirmed missing assets."""
    return check.url if check.available or check.status == 0 else None
