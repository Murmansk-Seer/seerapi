from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from typing import cast

import pytest
from sqlmodel import Session, SQLModel, create_engine

from seerapi_models.skill import SkillORM

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
    validate_regression_source,
    validate_skill_source,
)


def _skill(skill_id: int, effect_id: int, args: list[int]) -> SkillORM:
    return cast(
        SkillORM,
        SimpleNamespace(
            id=skill_id,
            skill_effect=[
                SimpleNamespace(
                    effect_id=effect_id,
                    args=list(args),
                    info='template {0}' if not args else 'formatted',
                    effect=SimpleNamespace(info='template {0}'),
                )
            ],
        ),
    )


@pytest.mark.parametrize('args', [[], [16], [16, 36, 31, 14, 2]])
def test_skill_gate_follows_empty_partial_and_filled_official_args(args):
    source = {'id': 29481, 'side_effect': [1866], 'side_effect_arg': args}
    validate_skill_source(_skill(29481, 1866, args), source)
    with pytest.raises(ValueError, match='differ from source'):
        validate_skill_source(_skill(29481, 1866, [*args, 999]), source)
    with pytest.raises(ValueError, match='differ from source'):
        validate_skill_source(_skill(29481, 495, args), source)


def test_empty_skill_template_still_cannot_be_filled_with_fake_values():
    skill = _skill(29481, 1866, [])
    skill.skill_effect[0].info = 'invented value'
    with pytest.raises(ValueError, match='template was altered'):
        validate_skill_source(
            skill, {'id': 29481, 'side_effect': [1866], 'side_effect_arg': []}
        )


def test_live_regressions_use_frozen_source_instead_of_hardcoded_old_values(tmp_path):
    unity = tmp_path / 'unity'
    unity.mkdir()
    moves = [
        {'id': 29481, 'side_effect': [1866], 'side_effect_arg': [16, 36, 31, 14, 2]},
        {'id': 38595, 'side_effect': [495], 'side_effect_arg': [37, 30]},
    ]
    (unity / 'moves.json').write_text(json.dumps({'root': {'moves': {'move': moves}}}))

    def activity_source(ending):
        (unity / 'ActivityCenter.json').write_text(
            json.dumps({'item': [{'id': 592, 'ending': ending}]})
        )

    activity_source('2026_11_05 24:00:00')
    activity = SimpleNamespace(
        end_time=datetime(2026, 11, 6, tzinfo=timezone(timedelta(hours=8)))
    )
    samples = {
        row['id']: _skill(row['id'], row['side_effect'][0], row['side_effect_arg'])
        for row in moves
    }
    fake = cast(
        Session,
        SimpleNamespace(
            get=lambda cls, key: samples[key] if cls is SkillORM else activity
        ),
    )
    validate_regression_source(fake, tmp_path)
    activity_source('2026_11_12 24:00:00')
    with pytest.raises(ValueError, match='differs from frozen official source'):
        validate_regression_source(fake, tmp_path)
    activity.end_time = datetime(2026, 11, 13, tzinfo=timezone(timedelta(hours=8)))
    validate_regression_source(fake, tmp_path)
    activity_source('2026_02_29 24:00:00')
    with pytest.raises(ValueError, match=r'.+'):
        validate_regression_source(fake, tmp_path)


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
