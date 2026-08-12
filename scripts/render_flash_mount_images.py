# SPDX-License-Identifier: MIT
"""Render Flash-only mount SWFs into PNG fallbacks for the runtime database."""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import os
import sqlite3
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
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


def _ensure_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS flash_mount_image (
            mount_id INTEGER PRIMARY KEY,
            png_data BLOB NOT NULL,
            source_url TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS flash_mount_image_pending (
            mount_id INTEGER PRIMARY KEY,
            source_url TEXT NOT NULL,
            last_checked_at REAL NOT NULL,
            last_error TEXT NOT NULL
        );
        """
    )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _copy_previous_state(
    connection: sqlite3.Connection,
    previous_database: Path | None,
) -> None:
    if previous_database is None or not previous_database.is_file():
        return
    with sqlite3.connect(previous_database) as previous:
        if _table_exists(previous, "flash_mount_image"):
            rows = previous.execute(
                """
                SELECT mount_id, png_data, source_url, source_sha256, updated_at
                FROM flash_mount_image
                """
            ).fetchall()
            connection.executemany(
                """
                INSERT OR IGNORE INTO flash_mount_image (
                    mount_id, png_data, source_url, source_sha256, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
        if _table_exists(previous, "flash_mount_image_pending"):
            rows = previous.execute(
                """
                SELECT mount_id, source_url, last_checked_at, last_error
                FROM flash_mount_image_pending
                """
            ).fetchall()
            connection.executemany(
                """
                INSERT OR IGNORE INTO flash_mount_image_pending (
                    mount_id, source_url, last_checked_at, last_error
                ) VALUES (?, ?, ?, ?)
                """,
                rows,
            )
    connection.execute(
        """
        DELETE FROM flash_mount_image_pending
        WHERE mount_id IN (SELECT mount_id FROM flash_mount_image)
        """
    )


def _candidate_mount_ids(connection: sqlite3.Connection) -> tuple[int, ...]:
    pending_ids = {
        int(row[0])
        for row in connection.execute(
            "SELECT mount_id FROM flash_mount_image_pending"
        )
    }
    if _table_exists(connection, "equip"):
        pending_ids.update(
            int(row[0])
            for row in connection.execute(
                "SELECT id FROM equip WHERE part_type_id = 6"
            )
        )
    # Keep the release-index source too: it permits a newly indexed mount to
    # receive a fallback even if a transient source build has not populated
    # the normal equipment table yet.
    if _table_exists(connection, "new_content_item"):
        pending_ids.update(
            int(row[0])
            for row in connection.execute(
                """
                SELECT entity_id
                FROM new_content_item
                WHERE category = 'mount'
                """
            )
        )
    existing_ids = {
        int(row[0])
        for row in connection.execute("SELECT mount_id FROM flash_mount_image")
    }
    return tuple(sorted(mount_id for mount_id in pending_ids if mount_id not in existing_ids))


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


def _record_pending(
    connection: sqlite3.Connection,
    mount_id: int,
    source_url: str,
    error: Exception,
) -> None:
    connection.execute(
        """
        INSERT INTO flash_mount_image_pending (
            mount_id, source_url, last_checked_at, last_error
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(mount_id) DO UPDATE SET
            source_url = excluded.source_url,
            last_checked_at = excluded.last_checked_at,
            last_error = excluded.last_error
        """,
        (mount_id, source_url, time.time(), str(error)[:500]),
    )


def refresh_mount_images(
    database: Path,
    *,
    previous_database: Path | None = None,
) -> RefreshResult:
    """Carry previous PNGs forward and retry new or pending Flash mount assets."""

    attempted = 0
    rendered = 0
    with sqlite3.connect(database) as connection:
        _ensure_tables(connection)
        _copy_previous_state(connection, previous_database)
        candidates = _candidate_mount_ids(connection)
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
                logger.info("Flash mount fallback unavailable for %s: %s", mount_id, error)
                _record_pending(connection, mount_id, source_url, error)
                continue
            connection.execute(
                """
                INSERT INTO flash_mount_image (
                    mount_id, png_data, source_url, source_sha256, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mount_id) DO UPDATE SET
                    png_data = excluded.png_data,
                    source_url = excluded.source_url,
                    source_sha256 = excluded.source_sha256,
                    updated_at = excluded.updated_at
                """,
                (
                    mount_id,
                    png_data,
                    source_url,
                    hashlib.sha256(swf_data).hexdigest(),
                    time.time(),
                ),
            )
            connection.execute(
                "DELETE FROM flash_mount_image_pending WHERE mount_id = ?",
                (mount_id,),
            )
            rendered += 1
        pending = int(
            connection.execute("SELECT count(*) FROM flash_mount_image_pending")
            .fetchone()[0]
        )
    return RefreshResult(attempted=attempted, rendered=rendered, pending=pending)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render pending Flash mount assets into PNG fallback rows."
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args()
    result = refresh_mount_images(args.database, previous_database=args.previous)
    logger.info(
        "Flash mount fallback: attempted=%s rendered=%s pending=%s",
        result.attempted,
        result.rendered,
        result.pending,
    )


if __name__ == "__main__":
    main()
