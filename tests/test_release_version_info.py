from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from new_content_index_models import SEMANTIC_SCHEMA_VERSION
from release_version_info import release_version_info


def _database(path: Path, version: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE seerapi_metadata (key TEXT, value TEXT)')
        connection.execute(
            'INSERT INTO seerapi_metadata VALUES (?, ?)',
            ('config_package_version', version),
        )


def test_release_version_info_reads_current_schema_and_cycle(tmp_path: Path) -> None:
    previous = tmp_path / 'previous.sqlite'
    current = tmp_path / 'current.sqlite'
    _database(previous, '20260924175611')
    _database(current, '20260927120000')
    with sqlite3.connect(previous) as connection:
        connection.execute(
            'CREATE TABLE new_content_release '
            '(id INTEGER PRIMARY KEY, schema_version INTEGER, weekly_cycle TEXT)'
        )
        connection.execute(
            'INSERT INTO new_content_release VALUES (1, 6, ?)',
            ('2026-09-18T00:00:00+00:00',),
        )

    assert release_version_info(previous, current, '2026-09-25T00:00:00+00:00') == (
        SEMANTIC_SCHEMA_VERSION,
        6,
        '20260924175611',
        '2026-09-18T00:00:00+00:00',
        '20260927120000',
        '2026-09-25T00:00:00+00:00',
    )


def test_release_version_info_supports_legacy_release_table(tmp_path: Path) -> None:
    previous = tmp_path / 'previous.sqlite'
    current = tmp_path / 'current.sqlite'
    _database(previous, '20260918180640')
    _database(current, '20260927120000')
    with sqlite3.connect(previous) as connection:
        connection.execute(
            'CREATE TABLE new_content_release '
            '(id INTEGER PRIMARY KEY, schema_version INTEGER)'
        )
        connection.execute('INSERT INTO new_content_release VALUES (1, 2)')

    result = release_version_info(previous, current, 'cycle')

    assert result[:4] == (SEMANTIC_SCHEMA_VERSION, 2, '20260918180640', 'unknown')
