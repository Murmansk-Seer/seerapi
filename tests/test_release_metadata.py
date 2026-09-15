# SPDX-License-Identifier: MIT
"""Tests for the published release metadata projection."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from release_metadata import replace_release_metadata


def test_replace_release_metadata_upserts_current_values() -> None:
    conn = sqlite3.connect(":memory:")

    replace_release_metadata(conn, {"built_at": "1", "source": "first"})
    replace_release_metadata(conn, {"built_at": "2", "source": "first"})

    assert conn.execute(
        "SELECT key, value FROM seerapi_metadata ORDER BY key"
    ).fetchall() == [("built_at", "2"), ("source", "first")]
