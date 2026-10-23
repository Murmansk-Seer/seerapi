import struct
from typing import get_args

from sqlmodel import SQLModel

from seerapi._typing import NamedModelName
import seerapi_models  # noqa: F401
from seerapi_models.items import Factor
from solaris.parse.parsers.fragment import FragmentParser


def test_factor_parser_retains_source_ids_and_exchange_parameters():
    fields = [2400001, 1, 2, 3, 4, 5, 6, 7, 1, 9, 10, 1]
    data = b'\x01\x01' + struct.pack('<i', 1) + struct.pack('<12i', *fields)
    parsed = FragmentParser().parse(data)
    assert parsed['root'] is not None
    row = parsed['root']['fragment'][0]
    assert row['id'] == 2400001
    assert row['move_id'] == 2
    assert row['moves_consume'] == 3
    assert row['effect_id'] == 10
    assert row['pet_consume'] == 7


def test_additive_factor_schema_and_existing_contract_are_registered():
    assert Factor.resource_name() == 'factor'
    assert 'factor' in get_args(NamedModelName)
    assert {'factor', 'factor_design', 'pet', 'skill', 'autocard_role'} <= set(
        SQLModel.metadata.tables
    )


def test_official_empty_soulmark_referenced_by_factor_is_retained(monkeypatch):
    from solaris.analyze.analyzers.pet.soulmark import SoulmarkAnalyzer

    empty = {
        'id': 769,
        'pet_id': [],
        'effect_id': 0,
        'kind': [],
        'tips': '',
        'analyze': '',
        'intensify': 0,
        'to': 0,
    }
    source = {
        'fragment.json': {'root': {'fragment': [{'effect_id': 769}]}},
        'effectIcon.json': {'root': {'effect': [empty, dict(empty, id=770)]}},
        'effectag.json': {'data': []},
        'petEffectIcon.json': {'data': []},
    }
    analyzer = object.__new__(SoulmarkAnalyzer)
    monkeypatch.setattr(analyzer, '_get_data', lambda _, name: source[name])
    rows = analyzer.analyze()[0].data
    assert set(rows) == {769}
    assert rows[769].desc == ''
    assert rows[769].pet == []
    assert rows[769].effect is None
    assert empty['pet_id'] == []


def test_neutral_spell_uses_existing_official_none_element(monkeypatch):
    from solaris.analyze.analyzers.autocard.analyzer import AutocardCardAnalyzer

    card = {
        'id': 20001,
        'type': 2,
        'nature': 0,
        'compose': 0,
        'name': '金币卡',
        'card_txt': '获得1枚金币',
        'level': 1,
        'cost': 1,
    }
    analyzer = object.__new__(AutocardCardAnalyzer)
    for name, value in {
        'autocard_content_data': {20001: card},
        'autocard_nature_data': {999: {'name': '无'}},
        'autocard_role_data': {},
        'autocard_field_buff_data': {},
    }.items():
        setattr(analyzer, name, value)
    monkeypatch.setattr(analyzer, '_get_data', lambda *_: {2: {'name': '魔法卡'}})
    results = analyzer.analyze()
    assert results[0].data[20001].element_type.id == 999
    assert 999 in results[5].data
    assert card['nature'] == 0
