import json
from typing import ClassVar

from pydantic import BaseModel

from seerapi_models.dango import Dango
from seerapi_models.metadata import ApiMetadata
from seerapi_models.pet.soulmark import Soulmark
from solaris.analyze.output.data_outputter import JsonOutputter
from solaris.analyze.output.json_format import (
    MergedJsonOutputFormat,
    SplitJsonOutputFormat,
)


class DeclaredNames(BaseModel):
    id: int
    first: str
    second: str
    __name_fields__: ClassVar[list[str]] = ['first', 'second']

    @classmethod
    def resource_name(cls) -> str:
        return 'declared'


class Ordinary(BaseModel):
    id: int
    name: str

    @classmethod
    def resource_name(cls) -> str:
        return 'ordinary'


class Unnamed(BaseModel):
    id: int

    @classmethod
    def resource_name(cls) -> str:
        return 'unnamed'


def test_json_resource_list_uses_primary_declared_field(tmp_path):
    metadata = ApiMetadata(
        api_url='https://example.test',
        api_version='v1',
        generator_name='test',
        generator_version='1',
    )
    out = JsonOutputter(
        metadata=metadata, base_output_dir=tmp_path, data_output_dir='data'
    )
    entries = [
        (
            'soulmark',
            {1: Soulmark.model_construct(id=1, effect_alias='alias_123')},
            ['alias_123'],
        ),
        (
            'declared',
            {
                0: DeclaredNames(id=0, first='', second='not fallback'),
                2: DeclaredNames(id=2, first='first', second='second'),
            },
            ['', 'first'],
        ),
        ('ordinary', {3: Ordinary(id=3, name='ordinary')}, ['ordinary']),
        ('unnamed', {4: Unnamed(id=4)}, [None]),
        ('empty', {}, []),
    ]
    for resource, data, expected in entries:
        out._output_api_resource_list(data, resource)
        payload = json.loads(
            (tmp_path / 'v1' / 'data' / resource / 'index.json').read_text()
        )
        assert payload['count'] == len(data)
        assert [row['id'] for row in payload['results']] == list(data)
        assert [row['name'] for row in payload['results']] == expected


def test_dango_name_gene_and_cross_field_alias_union(tmp_path):
    metadata = ApiMetadata(
        api_url='https://example.test',
        api_version='v1',
        generator_name='test',
        generator_version='1',
    )
    out = JsonOutputter(
        metadata=metadata, base_output_dir=tmp_path, data_output_dir='data'
    )
    data = {
        1: Dango.model_construct(id=1, name='shared', gene='gene_A'),
        2: Dango.model_construct(id=2, name='official', gene='shared'),
    }
    for fmt, resource in [
        (SplitJsonOutputFormat, 'dango'),
        (MergedJsonOutputFormat, 'dango_merged'),
    ]:
        fmt.write_resource(
            out, resource_name=resource, model=Dango, data=data, output_named_data=True
        )
    root = tmp_path / 'v1' / 'data'
    listing = json.loads((root / 'dango' / 'index.json').read_text(encoding='utf-8'))
    assert [item['name'] for item in listing['results']] == ['shared', 'official']
    detail = json.loads(
        (root / 'dango' / '1' / 'index.json').read_text(encoding='utf-8')
    )
    assert detail['name'] == 'shared'
    assert detail['gene'] == 'gene_A'
    shared = json.loads(
        (root / 'dango' / 'shared' / 'index.json').read_text(encoding='utf-8')
    )
    assert set(shared['data']) == {'1', '2'}
    gene = json.loads(
        (root / 'dango' / 'gene_A' / 'index.json').read_text(encoding='utf-8')
    )
    assert set(gene['data']) == {'1'}
    merged = json.loads(
        (root / 'dango_merged' / 'name.json').read_text(encoding='utf-8')
    )
    assert set(merged['shared']['data']) == {'1', '2'}
    assert set(merged['gene_A']['data']) == {'1'}
