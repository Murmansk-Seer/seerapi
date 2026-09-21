from pathlib import Path
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from autocard_sources import load_autocard_data


def test_load_autocard_data_normalizes_all_source_envelopes() -> None:
    payloads = {
        'content.json': ({'data': [{'id': 1}, 'skip']}, 'content-source'),
        'nature.json': ({'data': [{'id': 2}]}, 'nature-source'),
        'role.json': ({'data': 'not-a-list'}, 'role-source'),
        'buff.json': ({'data': [{'id': 3}]}, 'buff-source'),
    }

    data = load_autocard_data(
        payloads.__getitem__,
        content_file='content.json',
        nature_file='nature.json',
        role_file='role.json',
        buff_file='buff.json',
    )

    assert data.cards == [{'id': 1}]
    assert data.natures == [{'id': 2}]
    assert data.roles == []
    assert data.buffs == [{'id': 3}]
    assert data.source == 'buff-source\ncontent-source\nnature-source\nrole-source'
