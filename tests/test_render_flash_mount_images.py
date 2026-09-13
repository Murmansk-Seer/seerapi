from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

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
    unity_mount_ids: tuple[int, ...] = (),
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
        connection.execute(
            """
            CREATE TABLE render_asset_manifest (
                asset_kind TEXT NOT NULL,
                asset_key TEXT NOT NULL,
                available INTEGER NOT NULL,
                source TEXT NOT NULL
            )
            """
        )
        repository = "example/unity-assets"
        revision = "a" * 40
        connection.executemany(
            "INSERT INTO render_asset_manifest VALUES ('mount', ?, 1, ?)",
            (
                (
                    str(mount_id),
                    f"{repository}@{revision}:equip/{mount_id}.png#blob:abc",
                )
                for mount_id in unity_mount_ids
            ),
        )
        connection.execute(
            "CREATE TABLE ironsbot_metadata (key TEXT PRIMARY KEY, value TEXT)",
        )
        connection.execute(
            "INSERT INTO ironsbot_metadata VALUES "
            "('render_asset_manifest_repositories', ?)",
            (
                json.dumps(
                    {
                        "default": {
                            "repository": repository,
                            "revision": revision,
                        },
                        "mount": {
                            "repository": "example/generated-assets",
                            "revision": "b" * 40,
                        },
                    }
                ),
            ),
        )


def test_all_flash_mounts_are_retried_and_promoted_to_png(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "current.sqlite"
    output_dir = tmp_path / "mount"
    pending = tmp_path / "pending.txt"
    _database(database, (1301170,))

    def missing(_url: str) -> bytes:
        raise ValueError("404 Not Found")

    monkeypatch.setattr(renderer, "_download_swf", missing)
    first = renderer.refresh_mount_images(
        database, output_dir=output_dir, pending_output=pending
    )

    assert first.attempted == 1
    assert first.rendered == 0
    assert first.pending == 1
    assert pending.read_text(encoding="utf-8") == "1301170\n"

    monkeypatch.setattr(renderer, "_download_swf", lambda _url: b"CWS-mount")
    monkeypatch.setattr(renderer, "_render_swf_to_png", lambda _data, _id: b"png")
    second = renderer.refresh_mount_images(
        database, output_dir=output_dir, pending_output=pending
    )

    assert second.attempted == 1
    assert second.rendered == 1
    assert second.pending == 0
    assert (output_dir / "1301170.png").read_bytes() == b"png"
    assert pending.read_text(encoding="utf-8") == ""


def test_previous_flash_mount_rows_are_carried_forward(tmp_path: Path) -> None:
    previous = tmp_path / "previous.sqlite"
    current = tmp_path / "current.sqlite"
    _database(previous)
    _database(current, (7,))
    with sqlite3.connect(previous) as connection:
        connection.execute(
            "CREATE TABLE flash_mount_image ("
            "mount_id INTEGER PRIMARY KEY, png_data BLOB NOT NULL)"
        )
        connection.execute(
            "INSERT INTO flash_mount_image VALUES (7, ?)",
            (b"previous-png",),
        )

    output_dir = tmp_path / "mount"
    result = renderer.refresh_mount_images(
        current,
        output_dir=output_dir,
        previous_database=previous,
    )

    assert result == renderer.RefreshResult(attempted=0, rendered=0, pending=0)
    assert (output_dir / "7.png").read_bytes() == b"previous-png"


def test_mount_plan_identifies_only_uncached_generated_assets(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite"
    output_dir = tmp_path / "mount"
    output_dir.mkdir()
    (output_dir / "8.png").write_bytes(b"cached-generated-png")
    (output_dir / "99.png").write_bytes(b"retired-png")
    _database(database, (7, 8, 9), unity_mount_ids=(7,))

    plan = renderer.plan_mount_images(database, output_dir=output_dir)

    assert plan == renderer.MountImagePlan(
        mount_ids=(8, 9),
        candidate_ids=(9,),
    )
    assert plan.needs_render is True
    assert not (output_dir / "7.png").exists()
    assert not (output_dir / "99.png").exists()
    assert (output_dir / "8.png").read_bytes() == b"cached-generated-png"


def test_mount_plan_skips_renderer_when_generated_assets_are_complete(
    tmp_path: Path,
) -> None:
    database = tmp_path / "current.sqlite"
    output_dir = tmp_path / "mount"
    output_dir.mkdir()
    (output_dir / "8.png").write_bytes(b"cached-generated-png")
    _database(database, (7, 8), unity_mount_ids=(7,))

    plan = renderer.plan_mount_images(database, output_dir=output_dir)

    assert plan.candidate_ids == ()
    assert plan.needs_render is False


def test_unity_mounts_are_removed_from_generated_asset_branch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "current.sqlite"
    output_dir = tmp_path / "mount"
    output_dir.mkdir()
    (output_dir / "7.png").write_bytes(b"redundant-generated-png")
    _database(database, (7, 8), unity_mount_ids=(7,))
    requested: list[str] = []

    def download(url: str) -> bytes:
        requested.append(url)
        return b"CWS-mount"

    monkeypatch.setattr(renderer, "_download_swf", download)
    monkeypatch.setattr(renderer, "_render_swf_to_png", lambda _data, _id: b"png")

    result = renderer.refresh_mount_images(database, output_dir=output_dir)

    assert result == renderer.RefreshResult(attempted=1, rendered=1, pending=0)
    assert requested == [renderer._source_url(8)]
    assert not (output_dir / "7.png").exists()
    assert (output_dir / "8.png").read_bytes() == b"png"


def test_generated_manifest_fact_does_not_prune_its_own_asset(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite"
    output_dir = tmp_path / "mount"
    output_dir.mkdir()
    (output_dir / "7.png").write_bytes(b"generated-png")
    _database(database, (7,))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO render_asset_manifest VALUES ('mount', '7', 1, ?)",
            (f"example/generated-assets@{'b' * 40}:mount/7.png#blob:def",),
        )

    result = renderer.refresh_mount_images(database, output_dir=output_dir)

    assert result == renderer.RefreshResult(attempted=0, rendered=0, pending=0)
    assert (output_dir / "7.png").read_bytes() == b"generated-png"


def test_current_manifest_metadata_is_required(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite"
    _database(database, (7,))
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM ironsbot_metadata")

    with pytest.raises(
        ValueError,
        match="current render asset repository metadata is missing",
    ):
        renderer.refresh_mount_images(database, output_dir=tmp_path / "mount")


def test_retired_mount_assets_are_pruned(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite"
    output_dir = tmp_path / "mount"
    output_dir.mkdir()
    (output_dir / "7.png").write_bytes(b"retired")
    (output_dir / "8.png").write_bytes(b"current")
    _database(database, (8,))

    result = renderer.refresh_mount_images(database, output_dir=output_dir)

    assert result == renderer.RefreshResult(attempted=0, rendered=0, pending=0)
    assert not (output_dir / "7.png").exists()
    assert (output_dir / "8.png").read_bytes() == b"current"


def test_runtime_database_drops_legacy_mount_blob_tables(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite"
    _database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE flash_mount_image ("
            "mount_id INTEGER PRIMARY KEY, png_data BLOB NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE flash_mount_image_pending (mount_id INTEGER PRIMARY KEY)"
        )

    renderer.refresh_mount_images(database, output_dir=tmp_path / "mount")

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "flash_mount_image" not in tables
    assert "flash_mount_image_pending" not in tables
