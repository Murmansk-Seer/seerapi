import json
from pathlib import Path

from replay_somua_fixture import replay


def test_fixture_replay_uses_the_production_v1_resource_base(tmp_path: Path) -> None:
    counts = replay(tmp_path)
    for kind in ('data', 'sharded_data'):
        index = json.loads(
            (tmp_path / 'v1' / kind / 'index.json').read_text(encoding='utf-8')
        )
        assert set(index) - {'hash'} == set(counts)
        for resource in counts:
            assert index[resource] == f'https://api.seerapi.com/v1/{resource}'
