import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
from typing import Any, cast

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from seerapi_models.somua import SOMUA_RESOURCES
from seerapi_models.somua_source import load_somua_source, validate_somua_source
from solaris.analyze.analyzers.somua import SomuaAnalyzer
from solaris.parse import import_parser_classes

FIXTURES = Path(__file__).parents[1] / 'fixtures' / 'somua'
EVIDENCE = json.loads((FIXTURES / 'client-evidence.json').read_text('utf-8'))
PARSERS = {
    cls.source_config_filename()[:-6]: cls
    for cls in import_parser_classes()
    if cls.source_config_filename()[:-6] in EVIDENCE['tables']
}


def snake(value):
    value = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', value)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', value).lower()


@pytest.mark.parametrize('stem', ['SomuaBasicAttritube', 'SomuaModelConfig'])
def test_incompatible_old_layout_is_rejected(stem):
    raw = (FIXTURES / 'obsolete-20261105' / f'{stem}.bytes').read_bytes()
    with pytest.raises((ValueError, IndexError)):
        PARSERS[stem]().parse(raw)


@pytest.mark.parametrize('payload', [b'\xff', b'\xff\xff\x00'])
def test_current_model_rejects_invalid_utf8_and_string_length(payload):
    raw = b'\x01' + struct.pack('<iH', 1, len(payload)) + payload + b'\x00' * 8
    with pytest.raises(
        ValueError, match=r'row=0 .*field=addon_pool offset=5'
    ) as caught:
        PARSERS['SomuaModelConfig']().parse(raw)
    assert isinstance(caught.value.__cause__, UnicodeError)


def test_current_model_rejects_truncated_string_without_fallback():
    with pytest.raises(ValueError, match='field=addon_pool offset=5') as caught:
        PARSERS['SomuaModelConfig']().parse(
            b'\x01' + struct.pack('<iH', 1, 65535) + b'\x00' * 8
        )
    assert isinstance(caught.value.__cause__, IndexError)


@pytest.mark.parametrize('stem', EVIDENCE['tables'])
def test_full_client_fixture(stem):
    evidence = EVIDENCE['tables'][stem]
    assert {item['kind'] for item in evidence['loading_evidence']} == {
        'config asset literal',
        'Parse caller',
    }
    raw = (FIXTURES / f'{stem}.bytes').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence['sha256']
    result = PARSERS[stem]().parse(raw)
    assert list(result['data'][0]) == [
        snake(field['source']) for field in evidence['fields']
    ]
    expected = [
        {snake(key): value for key, value in row.items()} for row in evidence['rows']
    ]
    assert result == {'data': expected}
    assert len(result['data']) == evidence['count']
    assert len({row['id'] for row in expected}) == len(expected)
    model = SOMUA_RESOURCES[f'{stem}.json']
    assert [
        model.model_validate(row, strict=True).model_dump() for row in expected
    ] == expected


@pytest.mark.parametrize('stem', EVIDENCE['tables'])
def test_reject_damaged_or_trailing_bytes(stem):
    parser = PARSERS[stem]()
    raw = (FIXTURES / f'{stem}.bytes').read_bytes()
    for damaged in (b'', raw[:-1], raw + b'\x00', b'\x01' + struct.pack('<i', -1)):
        with pytest.raises((ValueError, IndexError, UnicodeError)):
            parser.parse(damaged)
    assert parser.parse(b'\x00') == {'data': []}
    with pytest.raises(ValueError, match='Unconsumed'):
        parser.parse(b'\x00\x00')
    # Repeat the exact first complete row from the client-verified fixture.
    one = EVIDENCE['tables'][stem]['rows'][0]
    fields = EVIDENCE['tables'][stem]['fields']
    encoded = bytearray()
    for field in fields:
        value = one[field['source']]
        if field['type'] == 'string':
            data = value.encode('utf-8')
            encoded.extend(struct.pack('<H', len(data)) + data)
        elif field['type'] == 'int32[]':
            encoded.extend(bytes([value is not None]))
            if value is not None:
                encoded.extend(struct.pack('<i', len(value)))
                for number in value:
                    encoded.extend(struct.pack('<i', number))
        else:
            encoded.extend(struct.pack('<i', value))
    with pytest.raises(ValueError, match='Duplicate'):
        parser.parse(b'\x01' + struct.pack('<i', 2) + encoded * 2)


def prepare_source(tmp_path):
    unity = tmp_path / 'unity'
    unity.mkdir()
    data = {}
    for stem, parser in PARSERS.items():
        parsed = parser().parse((FIXTURES / f'{stem}.bytes').read_bytes())
        (unity / f'{stem}.json').write_text(json.dumps(parsed), 'utf-8')
        data[f'{stem}.json'] = parsed
    analyzer = SomuaAnalyzer.__new__(SomuaAnalyzer)
    analyzer.data = {'unity': data}
    return analyzer


def test_analyze_sqlite_exact_source(tmp_path):
    analyzer = prepare_source(tmp_path)
    results = analyzer.analyze()
    assert len(results) == 27
    engine = create_engine(f'sqlite:///{tmp_path / "somua.sqlite"}')
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for result in results:
            session.add_all([row.to_orm() for row in result.data.values()])
        session.commit()
        for result in results:
            orm = result.model.get_orm_model()
            actual = {row.id: row.model_dump() for row in session.exec(select(orm))}
            assert actual == {key: row.model_dump() for key, row in result.data.items()}
    with sqlite3.connect(tmp_path / 'somua.sqlite') as connection:
        validate_somua_source(connection, tmp_path)
        connection.execute('UPDATE somua_model SET name = ?', ('drift',))
        with pytest.raises(ValueError, match='differs'):
            validate_somua_source(connection, tmp_path)
    (tmp_path / 'unity' / 'dango.json').unlink()
    with pytest.raises(FileNotFoundError):
        load_somua_source(tmp_path)


def test_discovery_and_separate_domains():
    discovered = set(import_parser_classes())
    assert set(PARSERS.values()) <= discovered
    assert len({model.resource_name() for model in SOMUA_RESOURCES.values()}) == 27
    assert SOMUA_RESOURCES['dango.json'] is not SOMUA_RESOURCES['SomuaModelConfig.json']


def test_null_empty_zero_unknown_and_type_drift(tmp_path):
    analyzer = prepare_source(tmp_path)
    rows = cast(
        list[dict[str, Any]],
        analyzer._get_data('unity', 'dangoAction.json')['data'],
    )
    for index, value in enumerate((None, [], [0, -1, 999999])):
        rows[index]['dango_id'] = value
    rows[0]['id'] = 0
    rows[0]['action'] = ''
    rows[0]['limit_type'] = 999999
    result = next(
        r for r in analyzer.analyze() if r.model.resource_name() == 'dango_action'
    )
    assert result.data[0].dango_id is None
    assert result.data[rows[1]['id']].dango_id == []
    rows[0]['extra_field'] = 1
    with pytest.raises(ValueError, match='field drift'):
        analyzer.analyze()
