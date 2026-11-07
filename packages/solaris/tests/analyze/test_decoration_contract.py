import json
from pathlib import Path

import pytest

from solaris.analyze.analyzers.decoration import DecorationAnalyzer
from solaris.analyze.base import DataImportConfig
from solaris.analyze.settings import DataSourceDirSettings


def test_generated_decoration_resources_are_all_declared_for_schema_exports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unity = tmp_path / 'unity'
    unity.mkdir()
    rows = [
        {'id': i, 'type': i, 'name': '', 'desc': '', 'icon': 0} for i in range(1, 7)
    ]
    (unity / 'profilephoto.json').write_text(json.dumps({'root': {'item': rows}}))
    monkeypatch.setattr(
        DataImportConfig,
        'SOURCE_DIR_SETTINGS',
        DataSourceDirSettings(BASE_DIR=tmp_path),
    )
    results = DecorationAnalyzer().analyze()
    assert {r.model for r in results} == set(DecorationAnalyzer.get_result_res_models())
    assert 'emoji' in {r.model.resource_name() for r in results}
