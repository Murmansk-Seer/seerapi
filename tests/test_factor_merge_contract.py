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
