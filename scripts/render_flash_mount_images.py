# SPDX-License-Identifier: MIT
"""Render Flash-only mount SWFs into publishable PNG assets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import io
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, UnidentifiedImageError

FLASH_MOUNT_ASSET_BASE_URL = os.environ.get(
    "IRONSBOT_DATA_FLASH_MOUNT_ASSET_BASE_URL",
    "https://seer.61.com/resource/item/cloth/swf/",
)
FLASH_MOUNT_RENDER_FFDEC_JAR = Path(
    os.environ.get("IRONSBOT_DATA_FLASH_MOUNT_RENDER_FFDEC_JAR", "ffdec.jar")
)
FLASH_MOUNT_RENDER_JAVA_COMMAND = os.environ.get(
    "IRONSBOT_DATA_FLASH_MOUNT_RENDER_JAVA_COMMAND", "java"
)
FLASH_MOUNT_RENDER_ZOOM = max(
    1,
    int(os.environ.get("IRONSBOT_DATA_FLASH_MOUNT_RENDER_ZOOM", "3")),
)
FLASH_MOUNT_RENDER_TIMEOUT_SECONDS = max(
    1,
    float(os.environ.get("IRONSBOT_DATA_FLASH_MOUNT_RENDER_TIMEOUT_SECONDS", "45")),
)
FLASH_MOUNT_DOWNLOAD_TIMEOUT_SECONDS = max(
    1,
    float(
        os.environ.get("IRONSBOT_DATA_FLASH_MOUNT_DOWNLOAD_TIMEOUT_SECONDS", "20")
    ),
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    attempted: int
    rendered: int
    pending: int


def _source_url(mount_id: int) -> str:
    return f"{FLASH_MOUNT_ASSET_BASE_URL.rstrip('/')}/{mount_id}.swf"


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _extract_previous_images(
    output_dir: Path,
    previous_database: Path | None,
) -> None:
    if previous_database is None or not previous_database.is_file():
        return
    with sqlite3.connect(previous_database) as previous:
        if _table_exists(previous, "flash_mount_image"):
            rows = previous.execute(
                "SELECT mount_id, png_data FROM flash_mount_image"
            ).fetchall()
            for mount_id, png_data in rows:
                path = output_dir / f"{int(mount_id)}.png"
                if not path.exists():
                    path.write_bytes(bytes(png_data))


def _mount_ids(connection: sqlite3.Connection) -> tuple[int, ...]:
    mount_ids: set[int] = set()
    if _table_exists(connection, "equip"):
        mount_ids.update(
            int(row[0])
            for row in connection.execute(
                "SELECT id FROM equip WHERE part_type_id = 6"
            )
        )
    # Keep the release-index source too: it permits a newly indexed mount to
    # receive a fallback even if a transient source build has not populated
    # the normal equipment table yet.
    if _table_exists(connection, "new_content_item"):
        mount_ids.update(
            int(row[0])
            for row in connection.execute(
                """
                SELECT entity_id
                FROM new_content_item
                WHERE category = 'mount'
                """
            )
        )
    return tuple(sorted(mount_ids))


def _mount_ids_requiring_generated_assets(
    connection: sqlite3.Connection,
    mount_ids: set[int],
) -> set[int]:
    default_prefix = _default_repository_source_prefix(connection)
    if default_prefix is None or not _table_exists(
        connection,
        "render_asset_manifest",
    ):
        return mount_ids
    unity_mount_ids = {
        int(asset_key)
        for asset_key, source in connection.execute(
            """
            SELECT asset_key, source
            FROM render_asset_manifest
            WHERE asset_kind = 'mount' AND available = 1
            """
        )
        if str(asset_key).isdigit() and str(source).startswith(default_prefix)
    }
    return mount_ids - unity_mount_ids


def _default_repository_source_prefix(
    connection: sqlite3.Connection,
) -> str | None:
    if not _table_exists(connection, "ironsbot_metadata"):
        return None
    row = connection.execute(
        "SELECT value FROM ironsbot_metadata "
        "WHERE key = 'render_asset_manifest_repositories'",
    ).fetchone()
    if row is None:
        return None
    try:
        default = json.loads(str(row[0]))["default"]
        repository = str(default["repository"])
        revision = str(default["revision"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not repository or not revision:
        return None
    return f"{repository}@{revision}:"


def _prune_retired_images(output_dir: Path, mount_ids: set[int]) -> None:
    for path in output_dir.glob("*.png"):
        if path.stem.isdigit() and int(path.stem) not in mount_ids:
            path.unlink()


def _download_swf(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "SeerAPI Flash mount fallback"})
    with urlopen(request, timeout=FLASH_MOUNT_DOWNLOAD_TIMEOUT_SECONDS) as response:
        data = response.read()
        content_type = str(response.headers.get("Content-Type", "")).lower()
    if not data.startswith((b"FWS", b"CWS", b"ZWS")) and "shockwave-flash" not in content_type:
        raise ValueError("Flash mount asset is not an SWF")
    return data


def _visible_pixel_count(data: bytes) -> int:
    try:
        with Image.open(io.BytesIO(data)) as image:
            return sum(image.convert("RGBA").getchannel("A").histogram()[1:])
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError("FFDec output is not a valid PNG") from error


def _select_item_sprite_png(output_dir: Path) -> bytes:
    candidates: list[tuple[int, bytes]] = []
    item_paths = [
        path
        for path in output_dir.rglob("*.png")
        if any(part.endswith("_item") for part in path.parts)
    ]
    for path in item_paths or list(output_dir.rglob("*.png")):
        data = path.read_bytes()
        if visible_pixels := _visible_pixel_count(data):
            candidates.append((visible_pixels, data))
    if not candidates:
        raise ValueError("FFDec produced no visible mount PNG")
    return max(candidates, key=lambda candidate: (candidate[0], len(candidate[1])))[1]


def _normalize_png(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as image:
            rgba = image.convert("RGBA")
            bounds = rgba.getchannel("A").getbbox()
            if bounds is None:
                raise ValueError("FFDec output is fully transparent")
            cropped = rgba.crop(bounds)
            side = max(cropped.size)
            normalized = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            normalized.alpha_composite(
                cropped,
                ((side - cropped.width) // 2, (side - cropped.height) // 2),
            )
            output = io.BytesIO()
            normalized.save(output, format="PNG")
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError("FFDec output is not a valid PNG") from error
    return output.getvalue()


def _render_swf_to_png(swf_data: bytes, mount_id: int) -> bytes:
    with tempfile.TemporaryDirectory(prefix="flash-mount-") as temp_dir:
        temp_path = Path(temp_dir)
        swf_path = temp_path / f"{mount_id}.swf"
        output_dir = temp_path / "sprites"
        swf_path.write_bytes(swf_data)
        output_dir.mkdir()
        completed = subprocess.run(
            [
                FLASH_MOUNT_RENDER_JAVA_COMMAND,
                "-jar",
                str(FLASH_MOUNT_RENDER_FFDEC_JAR),
                "-zoom",
                str(FLASH_MOUNT_RENDER_ZOOM),
                "-ignorebackground",
                "-format",
                "sprite:png",
                "-export",
                "sprite",
                str(output_dir),
                str(swf_path),
            ],
            check=False,
            capture_output=True,
            timeout=FLASH_MOUNT_RENDER_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).decode(
                "utf-8",
                errors="replace",
            ).strip()
            raise RuntimeError(f"FFDec exited {completed.returncode}: {message}")
        return _normalize_png(_select_item_sprite_png(output_dir))


def refresh_mount_images(
    database: Path,
    *,
    output_dir: Path,
    previous_database: Path | None = None,
    pending_output: Path | None = None,
) -> RefreshResult:
    """Reuse published PNGs and render assets not already present."""

    attempted = 0
    rendered = 0
    pending_ids: list[int] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    _extract_previous_images(output_dir, previous_database)
    with sqlite3.connect(database) as connection:
        mount_ids = set(_mount_ids(connection))
        generated_mount_ids = _mount_ids_requiring_generated_assets(
            connection,
            mount_ids,
        )
        _prune_retired_images(output_dir, generated_mount_ids)
        candidates = tuple(
            mount_id
            for mount_id in sorted(generated_mount_ids)
            if not (output_dir / f"{mount_id}.png").is_file()
        )
        for mount_id in candidates:
            attempted += 1
            source_url = _source_url(mount_id)
            try:
                swf_data = _download_swf(source_url)
                png_data = _render_swf_to_png(swf_data, mount_id)
            except (
                HTTPError,
                URLError,
                OSError,
                RuntimeError,
                subprocess.SubprocessError,
                ValueError,
            ) as error:
                logger.info("Flash mount asset unavailable for %s: %s", mount_id, error)
                pending_ids.append(mount_id)
                continue
            (output_dir / f"{mount_id}.png").write_bytes(png_data)
            rendered += 1
        connection.execute("DROP TABLE IF EXISTS flash_mount_image")
        connection.execute("DROP TABLE IF EXISTS flash_mount_image_pending")
    if pending_output is not None:
        pending_output.parent.mkdir(parents=True, exist_ok=True)
        pending_output.write_text(
            "".join(f"{mount_id}\n" for mount_id in pending_ids),
            encoding="utf-8",
        )
    return RefreshResult(
        attempted=attempted,
        rendered=rendered,
        pending=len(pending_ids),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render Flash mount assets into a publishable PNG directory."
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--pending-output", type=Path)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args()
    result = refresh_mount_images(
        args.database,
        output_dir=args.output_dir,
        previous_database=args.previous,
        pending_output=args.pending_output,
    )
    logger.info(
        "Flash mount assets: attempted=%s rendered=%s pending=%s",
        result.attempted,
        result.rendered,
        result.pending,
    )


if __name__ == "__main__":
    main()
