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
    / "finalize_render_asset_manifest.py"
)
SCRIPT_ROOT = SCRIPT_PATH.parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
SPEC = importlib.util.spec_from_file_location(
    "finalize_render_asset_manifest", SCRIPT_PATH
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError
finalizer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = finalizer
SPEC.loader.exec_module(finalizer)


def test_generated_snapshot_uses_publishable_relative_paths(tmp_path: Path) -> None:
    mount_dir = tmp_path / "mount"
    mount_dir.mkdir()
    (mount_dir / "7.png").write_bytes(b"png")

    snapshot = finalizer._generated_snapshot(
        mount_dir,
        repository="example/seerapi",
        revision="a" * 40,
    )

    assert snapshot.repository == "example/seerapi"
    assert snapshot.revision == "a" * 40
    assert tuple(snapshot.blobs_by_path) == ("mount/7.png",)
    assert snapshot.sha256_by_path == snapshot.blobs_by_path


def test_generated_snapshot_requires_immutable_revision(tmp_path: Path) -> None:
    mount_dir = tmp_path / "mount"
    mount_dir.mkdir()

    with pytest.raises(ValueError, match="full Git commit SHA"):
        finalizer._generated_snapshot(
            mount_dir,
            repository="example/seerapi",
            revision="main",
        )


def test_published_default_snapshot_reuses_verified_manifest_inventory() -> None:
    metadata = {
        finalizer.builder.RENDER_ASSET_MANIFEST_REPOSITORIES_KEY: json.dumps(
            {
                "default": {
                    "repository": "example/assets",
                    "revision": "a" * 40,
                }
            }
        )
    }
    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            "CREATE TABLE render_asset_manifest (available INTEGER, source TEXT)"
        )
        connection.executemany(
            "INSERT INTO render_asset_manifest VALUES (?, ?)",
            (
                (
                    1,
                    f"example/assets@{'a' * 40}:pet/7.png#blob:abc",
                ),
                (0, f"example/assets@{'a' * 40}:missing:pet/8.png"),
                (1, "ConfigPackage/effectIcon.bytes#v1"),
            ),
        )

        snapshot = finalizer._published_default_snapshot(connection, metadata)

    assert snapshot.blobs_by_path == {"pet/7.png": "abc"}


def test_finalize_manifest_publishes_mount_fact_without_sqlite_blob(
    tmp_path: Path,
) -> None:
    database = tmp_path / "release.sqlite"
    mount_dir = tmp_path / "mount"
    mount_dir.mkdir()
    (mount_dir / "7.png").write_bytes(b"png")
    (mount_dir / "8.png").write_bytes(b"generated-but-lower-priority")
    repositories = json.dumps(
        {
            "default": {
                "repository": "example/assets",
                "revision": "a" * 40,
            }
        }
    )
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE pet (resource_id INTEGER);
            CREATE TABLE element_type (id INTEGER);
            CREATE TABLE mintmark (id INTEGER);
            CREATE TABLE item (id INTEGER);
            CREATE TABLE special_effect_status (status_id INTEGER);
            CREATE TABLE suit (id INTEGER);
            CREATE TABLE equip (id INTEGER, part_type_id INTEGER);
            INSERT INTO equip VALUES (7, 6), (8, 6);
            CREATE TABLE title_part (id INTEGER);
            CREATE TABLE skin_image_resolution (
                skin_id INTEGER, head_resource_id INTEGER, body_resource_id INTEGER
            );
            CREATE TABLE pet_skin (id INTEGER, resource_id INTEGER);
            CREATE TABLE soulmark_icon (
                icon_id INTEGER, icon_png BLOB, icon_png_available INTEGER
            );
            CREATE TABLE render_asset_manifest (
                asset_kind TEXT, asset_key TEXT, sha256 TEXT,
                release_revision TEXT, available INTEGER, source TEXT,
                updated_at REAL, PRIMARY KEY (asset_kind, asset_key)
            );
            CREATE TABLE ironsbot_metadata (
                key TEXT PRIMARY KEY, value TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO render_asset_manifest VALUES (?, ?, '', 'release', 1, ?, 0)",
            (
                (
                    "pet_head",
                    "1",
                    f"example/assets@{'a' * 40}:pet/1.png#blob:abc",
                ),
                (
                    "mount",
                    "8",
                    f"example/assets@{'a' * 40}:"
                    "newseer/assets/art/ui/assets/item/cloth/prev/8.png#blob:unity",
                ),
            ),
        )
        connection.executemany(
            "INSERT INTO ironsbot_metadata VALUES (?, ?)",
            (
                (
                    finalizer.builder.RENDER_ASSET_MANIFEST_REPOSITORIES_KEY,
                    repositories,
                ),
                ("config_package_version", "release"),
                ("effect_icon_png_cache_version", "icons"),
            ),
        )

    finalizer.finalize_manifest(
        database,
        mount_directory=mount_dir,
        mount_repository="example/seerapi",
        mount_revision="b" * 40,
    )

    with sqlite3.connect(database) as connection:
        mount = connection.execute(
            "SELECT sha256, available, source FROM render_asset_manifest "
            "WHERE asset_kind = 'mount' AND asset_key = '7'"
        ).fetchone()
        unity_mount = connection.execute(
            "SELECT available, source FROM render_asset_manifest "
            "WHERE asset_kind = 'mount' AND asset_key = '8'"
        ).fetchone()
        published_repositories = connection.execute(
            "SELECT value FROM ironsbot_metadata "
            "WHERE key = 'render_asset_manifest_repositories'"
        ).fetchone()
    assert mount is not None
    assert mount[0] == finalizer.hashlib.sha256(b"png").hexdigest()
    assert mount[1] == 1
    assert str(mount[2]).startswith(f"example/seerapi@{'b' * 40}:mount/7.png")
    assert unity_mount == (
        1,
        f"example/assets@{'a' * 40}:"
        "newseer/assets/art/ui/assets/item/cloth/prev/8.png#blob:unity",
    )
    assert published_repositories is not None
    assert json.loads(published_repositories[0])["mount"]["revision"] == "b" * 40
