from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import pytest
from sqlmodel import SQLModel, create_engine

SCRIPT_DIRECTORY = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, SCRIPT_DIRECTORY)

from release_contract import (
    GENERATED_RELEASE_TABLES,
    SCHEMA_CONTRACT_VERSION,
    SCHEMA_CONTRACT_VERSION_KEY,
    SCHEMA_FINGERPRINT_KEY,
    SCHEMA_TABLES_KEY,
    finalize_release_contract,
    schema_fingerprint,
)


def _create_release(path: Path, *, omit: str | None = None) -> None:
    engine = create_engine(f'sqlite:///{path}')
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(path) as connection:
        for table in sorted(GENERATED_RELEASE_TABLES):
            if (
                table == omit
                or table == 'seerapi_metadata'
                or table in SQLModel.metadata.tables
            ):
                continue
            connection.execute(f'CREATE TABLE "{table}" (id INTEGER)')
        if omit != 'seerapi_metadata':
            connection.execute(
                'CREATE TABLE seerapi_metadata '
                '(key TEXT PRIMARY KEY, value TEXT NOT NULL)'
            )
        if omit in SQLModel.metadata.tables:
            connection.execute(f'DROP TABLE "{omit}"')
        if omit == 'seerapi_metadata':
            connection.commit()
            return
        connection.execute(
            'DELETE FROM seerapi_metadata WHERE key = ?',
            (SCHEMA_CONTRACT_VERSION_KEY,),
        )
        connection.execute(
            'INSERT INTO seerapi_metadata (key, value) VALUES (?, ?)',
            (SCHEMA_CONTRACT_VERSION_KEY, SCHEMA_CONTRACT_VERSION),
        )
        connection.commit()


def test_final_release_contract_publishes_complete_table_manifest(
    tmp_path: Path,
) -> None:
    database = tmp_path / 'release.sqlite'
    _create_release(database)

    tables = finalize_release_contract(database)

    with sqlite3.connect(database) as connection:
        metadata = dict(
            connection.execute(
                'SELECT key, value FROM seerapi_metadata WHERE key IN (?, ?)',
                (SCHEMA_TABLES_KEY, SCHEMA_FINGERPRINT_KEY),
            )
        )
        expected_fingerprint = schema_fingerprint(connection, tables)
    assert tuple(json.loads(metadata[SCHEMA_TABLES_KEY])) == tables
    assert metadata[SCHEMA_FINGERPRINT_KEY] == expected_fingerprint


def test_final_release_contract_rejects_missing_required_table(tmp_path: Path) -> None:
    database = tmp_path / 'release.sqlite'
    _create_release(database, omit='new_content_release')

    with pytest.raises(ValueError, match='new_content_release'):
        finalize_release_contract(database)


def test_final_release_contract_rejects_wrong_schema_version(tmp_path: Path) -> None:
    database = tmp_path / 'release.sqlite'
    _create_release(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            'UPDATE seerapi_metadata SET value = ? WHERE key = ?',
            ('0', SCHEMA_CONTRACT_VERSION_KEY),
        )
        connection.commit()

    with pytest.raises(ValueError, match='version mismatch'):
        finalize_release_contract(database)
