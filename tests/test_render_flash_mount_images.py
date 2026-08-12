from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import sys

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "render_flash_mount_images.py"
)
SPEC = importlib.util.spec_from_file_location("render_flash_mount_images", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
renderer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = renderer
SPEC.loader.exec_module(renderer)


def _database(
    path: Path,
    mount_ids: tuple[int, ...] = (),
    *,
    indexed_mount_ids: tuple[int, ...] = (),
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE equip (
                id INTEGER PRIMARY KEY,
                part_type_id INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            "INSERT INTO equip (id, part_type_id) VALUES (?, 6)",
            ((mount_id,) for mount_id in mount_ids),
        )
        connection.execute(
            """
            CREATE TABLE new_content_item (
                category TEXT, entity_id INTEGER, name TEXT, sort_value INTEGER,
                payload_json TEXT, change_kind TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO new_content_item VALUES ('mount', ?, '', ?, '{}', 'added')
            """,
            ((mount_id, mount_id) for mount_id in indexed_mount_ids),
        )


def test_all_flash_mounts_are_retried_and_promoted_to_png(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "current.sqlite"
    _database(database, (1301170,))

    def missing(_url: str) -> bytes:
        raise ValueError("404 Not Found")

    monkeypatch.setattr(renderer, "_download_swf", missing)
    first = renderer.refresh_mount_images(database)

    assert first.attempted == 1
    assert first.rendered == 0
    assert first.pending == 1

    monkeypatch.setattr(renderer, "_download_swf", lambda _url: b"CWS-mount")
    monkeypatch.setattr(renderer, "_render_swf_to_png", lambda _data, _id: b"png")
    second = renderer.refresh_mount_images(database)

    assert second.attempted == 1
    assert second.rendered == 1
    assert second.pending == 0
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT png_data FROM flash_mount_image WHERE mount_id = 1301170"
        ).fetchone() == (b"png",)


def test_previous_flash_mount_rows_are_carried_forward(tmp_path: Path) -> None:
    previous = tmp_path / "previous.sqlite"
    current = tmp_path / "current.sqlite"
    _database(previous)
    _database(current)
    with sqlite3.connect(previous) as connection:
        renderer._ensure_tables(connection)
        connection.execute(
            """
            INSERT INTO flash_mount_image VALUES (7, ?, 'https://example/7.swf', 'sha', 1)
            """,
            (b"previous-png",),
        )

    result = renderer.refresh_mount_images(current, previous_database=previous)

    assert result == renderer.RefreshResult(attempted=0, rendered=0, pending=0)
    with sqlite3.connect(current) as connection:
        assert connection.execute(
            "SELECT png_data FROM flash_mount_image WHERE mount_id = 7"
        ).fetchone() == (b"previous-png",)
