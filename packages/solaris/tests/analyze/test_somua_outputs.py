import importlib.util
import json
from pathlib import Path
import sqlite3

from seerapi import _model_map
from seerapi_models.somua import SOMUA_RESOURCES
from solaris.analyze.output.output_helpers import get_name_fields, is_named_model

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    'somua_replay', ROOT / 'scripts/replay_somua_fixture.py'
)
assert SPEC is not None
assert SPEC.loader is not None
REPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY)


def test_production_json_database_schema_and_openapi_outputs(tmp_path):
    counts = REPLAY.replay(tmp_path)
    assert len(counts) == 27
    root = tmp_path / 'v1'
    oad = json.loads((root / 'openapi.json').read_text('utf-8'))
    for filename, model in SOMUA_RESOURCES.items():
        resource = model.resource_name()
        assert counts[resource] > 0
        listing = json.loads(
            (root / 'data' / resource / 'index.json').read_text('utf-8')
        )
        assert listing['count'] == counts[resource]
        merged = json.loads(
            (root / 'merged_data' / resource / 'id.json').read_text('utf-8')
        )
        assert len(merged) - 1 == counts[resource]  # hash metadata is not a record.
        assert f'v1/{resource}/' in oad['paths']
        assert f'v1/{resource}/{{id}}' in oad['paths']
        assert (f'v1/{resource}/{{name}}' in oad['paths']) == is_named_model(model)
        assert model in _model_map.MODEL_MAP.values()
        for key, row in merged.items():
            if key == 'hash':
                continue
            detail = json.loads(
                (root / 'data' / resource / key / 'index.json').read_text('utf-8')
            )
            assert {k: v for k, v in detail.items() if k != 'hash'} == row
        if is_named_model(model):
            names = json.loads(
                (root / 'merged_data' / resource / 'name.json').read_text('utf-8')
            )
            for row in merged.values():
                if not isinstance(row, dict):
                    continue
                for field in get_name_fields(model):
                    if row[field].strip():
                        assert names[row[field].strip()]['data'][str(row['id'])] == row
        schema = oad['components']['schemas'][resource]['allOf'][1]
        for field in schema['properties']:
            assert field in model.model_fields or field == 'hash'
    with sqlite3.connect(tmp_path / 'seerapi-data.sqlite') as connection:
        assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
