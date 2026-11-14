import json
from pathlib import Path

import pytest

from solaris.parse import snapshot


class ExampleParser:
    @classmethod
    def source_config_filename(cls):
        return 'example.bytes'

    @classmethod
    def parsed_config_filename(cls):
        return 'example.json'

    def parse(self, data):
        return json.loads(data)


@pytest.fixture
def setup_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(snapshot, 'import_parser_classes', lambda: [ExampleParser])
    output = tmp_path / 'unity'
    output.mkdir()
    for name, data in {
        '.version': 'old',
        '.somua-version': 'old',
        '.parser-revision': 'old',
        'example.json': '{}',
        'fork-only.json': 'keep',
    }.items():
        (output / name).write_text(data)
    return output


def publish(output, data):
    snapshot.publish_unity_snapshot(
        data, output, version='20261113190033', parser_revision='a' * 40
    )


def test_complete_snapshot_updates_markers_and_preserves_fork_files(setup_snapshot):
    parsed = snapshot.parse_unity_snapshot({'example.bytes': b'{"data":[]}'})
    publish(setup_snapshot, parsed)
    assert (setup_snapshot / 'fork-only.json').read_text() == 'keep'
    assert json.loads((setup_snapshot / 'example.json').read_text()) == {'data': []}
    assert (setup_snapshot / '.version').read_text().strip() == '20261113190033'
    assert (setup_snapshot / '.somua-version').read_text() == (
        setup_snapshot / '.version'
    ).read_text()
    assert (setup_snapshot / '.parser-revision').read_text().strip() == 'a' * 40


@pytest.mark.parametrize(
    'assets', [{}, {'example.bytes': b'broken'}, {'example.bytes': b'{"value":NaN}'}]
)
def test_parse_failure_does_not_touch_live_outputs(setup_snapshot, assets):
    before = {p.name: p.read_bytes() for p in setup_snapshot.iterdir()}
    with pytest.raises(ValueError, match='Unity snapshot'):
        snapshot.parse_unity_snapshot(assets)
    assert before == {p.name: p.read_bytes() for p in setup_snapshot.iterdir()}


@pytest.mark.parametrize(
    'data', [{}, {'gems.json': {}}, {'example.json': {'bad': object()}}]
)
def test_partial_or_invalid_export_cannot_advance_versions(setup_snapshot, data):
    with pytest.raises((ValueError, TypeError)):
        publish(setup_snapshot, data)
    assert (setup_snapshot / '.version').read_text() == 'old'
    assert (setup_snapshot / 'example.json').read_text() == '{}'


def test_failed_directory_promotion_restores_old_snapshot(setup_snapshot, monkeypatch):
    original = Path.rename

    def rename(path, target):
        if path.name == 'candidate':
            raise OSError('promotion failed')
        return original(path, target)

    monkeypatch.setattr(Path, 'rename', rename)
    with pytest.raises(OSError, match='promotion failed'):
        publish(setup_snapshot, {'example.json': {'data': []}})
    assert (setup_snapshot / '.version').read_text() == 'old'
    assert (setup_snapshot / 'fork-only.json').read_text() == 'keep'


@pytest.mark.parametrize('name', ['../escape', '.version', 'example.json'])
def test_extras_cannot_escape_or_override_required_outputs(setup_snapshot, name):
    with pytest.raises(ValueError, match=r'Snapshot filenames|Extra snapshot'):
        snapshot.publish_unity_snapshot(
            {'example.json': {}},
            setup_snapshot,
            version='20261113190033',
            parser_revision='a' * 40,
            extra_files={name: b'bad'},
        )
    assert (setup_snapshot / '.version').read_text() == 'old'


def test_current_inventory_always_includes_every_somua_table_and_gems():
    sources = snapshot.required_unity_sources()
    assert 'gems.bytes' in sources
    assert {
        name.removesuffix('.json') + '.bytes' for name in snapshot.SOMUA_RESOURCES
    } <= sources
    assert len(sources) == 294
