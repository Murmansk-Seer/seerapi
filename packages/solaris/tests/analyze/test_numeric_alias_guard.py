import json
from pathlib import Path
from typing import Any

import pytest

from seerapi_models.metadata import ApiMetadata
from seerapi_models.sign import Sign
from solaris.analyze.output.data_outputter import JsonOutputter
from solaris.analyze.output.json_format import (
    JsonOutputFormat,
    MergedJsonOutputFormat,
    ShardedJsonOutputFormat,
    SplitJsonOutputFormat,
)


def records(pairs: list[tuple[int, str]]) -> dict[int, Sign]:
    return {i: Sign(id=i, name=n, sort=4, is_show_num=True) for i, n in pairs}


def write(tmp_path: Path, fmt: type[JsonOutputFormat], data: dict[int, Sign]) -> Path:
    m = ApiMetadata(
        api_url='https://example.invalid',
        api_version='v1',
        generator_name='test',
        generator_version='1',
    )
    o = JsonOutputter(metadata=m, base_output_dir=tmp_path, data_output_dir='data')
    fmt.write_resource(
        o, resource_name='sign', model=Sign, data=data, output_named_data=True
    )
    return tmp_path / 'v1/data/sign'


def read(p: Path) -> Any:
    return json.loads(p.read_text(encoding='utf8'))


@pytest.mark.parametrize(
    ('pairs', 'alias', 'ids'),
    [
        ([(2, 'shield'), (203, '2')], '2', '203'),
        (
            [(3, 'shield'), (204, '3'), (205, '3'), (206, '3'), (207, '3'), (208, '3')],
            '3',
            '204',
        ),
        ([(2, '2')], '2', '2'),
    ],
)
def test_collision_fails_before_resource_write(
    tmp_path: Path, pairs: list[tuple[int, str]], alias: str, ids: str
) -> None:
    with pytest.raises(ValueError, match='Split JSON resource') as exc:
        write(tmp_path, SplitJsonOutputFormat, records(pairs))
    assert 'sign' in str(exc.value)
    assert alias in str(exc.value)
    assert ids in str(exc.value)
    assert not (tmp_path / 'v1/data/sign').exists()


def test_split_noncollision_and_same_name_group(tmp_path: Path) -> None:
    p = write(
        tmp_path,
        SplitJsonOutputFormat,
        records([(2, '42'), (3, 'shared'), (4, 'shared')]),
    )
    assert read(p / '2/index.json')['id'] == 2
    assert set(read(p / '42/index.json')['data']) == {'2'}
    assert set(read(p / 'shared/index.json')['data']) == {'3', '4'}


@pytest.mark.parametrize('fmt', [MergedJsonOutputFormat, ShardedJsonOutputFormat])
def test_separate_formats_keep_numeric_and_duplicate_names(
    tmp_path: Path, fmt: type[JsonOutputFormat]
) -> None:
    data = records([(2, 'shield'), (3, 'shield'), (203, '2'), (204, '3'), (205, '3')])
    p = write(tmp_path, fmt, data)
    if fmt is MergedJsonOutputFormat:
        ids = read(p / 'id.json')
        names = read(p / 'name.json')
        assert set(ids).issuperset({'2', '3', '203', '204', '205'})
        assert set(names['2']['data']) == {'203'}
        assert set(names['3']['data']) == {
            '204',
            '205',
        }
        assert set(names['shield']['data']) == {'2', '3'}
    else:
        ids = read(p / 'id-index.json')['by_id']
        names = read(p / 'name-index.json')['by_name']
        assert set(ids) == {'2', '3', '203', '204', '205'}
        assert set(map(str, names['2'])) == {'203'}
        assert set(map(str, names['3'])) == {
            '204',
            '205',
        }
        assert set(map(str, names['shield'])) == {'2', '3'}
        for key, shard in ids.items():
            assert read(p / 'id/shards' / f'{shard}.json')[key]['id'] == int(key)
