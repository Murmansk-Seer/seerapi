#!/usr/bin/env python3
"""Add historical chip facts to a temporary prior-cycle comparison database."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sqlite3
from urllib.parse import urljoin

from build_http import BuildHttpClient, BuildHttpConfig, extract_text_assets
from config_package_sources import parse_autocard_chips, parse_package_manifest
from new_content_index_release import _config_version, _weekly_cycle
from release_autocard_tables import replace_autocard_chip_table

BASE_URL = 'https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/'


def backfill(path: Path, current_version: str) -> bool:
    with sqlite3.connect(path) as conn:
        existing = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'autocard_chip'"
        ).fetchone()
        if existing:
            return True
        previous_version = _config_version(conn)
        if _weekly_cycle(previous_version) >= _weekly_cycle(current_version):
            return False
        http = BuildHttpClient(
            BuildHttpConfig(timeout_seconds=30, retry_attempts=3, retry_backoff_seconds=2),
            logger=logging.getLogger(__name__),
        )
        try:
            manifest = parse_package_manifest(http.download_bytes(urljoin(
                BASE_URL,
                f'PackageManifest_ConfigPackage_{previous_version}.bytes',
            )))
            bundle = next(
                item for item in manifest.bundles if item.name == 'pgame_configs_bytes'
            )
            payload = extract_text_assets(
                http.download_bytes(urljoin(BASE_URL, bundle.file_hash)),
                {'autocardChip.bytes'},
            )['autocardChip.bytes']
            chips = parse_autocard_chips(payload)
        except (OSError, ValueError, KeyError, StopIteration) as error:
            logging.warning('Historical chip baseline unavailable: %s', error)
            return False
        replace_autocard_chip_table(conn, chips, 0.0)
        conn.commit()
        return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('previous_database', type=Path)
    parser.add_argument('current_version')
    args = parser.parse_args()
    status = (
        'ready'
        if backfill(args.previous_database, args.current_version)
        else 'unavailable'
    )
    print(f'chip baseline: {status}')  # noqa: T201 - workflow status


if __name__ == '__main__':
    main()
