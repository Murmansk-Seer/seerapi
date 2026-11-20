from pathlib import Path
import struct

import pytest

from solaris.parse.parsers.sp_hide_moves import SpHideMovesParser


def test_official_november_19_hidden_skills_are_complete():
    path = Path(__file__).parents[1] / 'fixtures/sp_hide_moves-20261119.bytes'
    raw = path.read_bytes()
    parser = SpHideMovesParser()
    result = parser.parse(raw)['config']
    for group in ('show_moves', 'sp_moves'):
        assert result[group]
        assert all(type(row['newse']) is int for row in result[group])
    with pytest.raises(ValueError, match='Unconsumed'):
        parser.parse(raw + b'\x00')
    with pytest.raises((IndexError, ValueError)):
        parser.parse(raw[:-1])


def test_newse_order_and_both_arrays():
    def row(id):
        return (
            struct.pack('<iiH', id, 0, 0)
            + struct.pack('<iiiH', 1, 3311, 123, 0)
            + struct.pack('<ii', 2, -17)
        )

    raw = b'\x01' + b''.join(b'\x01' + struct.pack('<i', 1) + row(id) for id in (1, 2))
    result = SpHideMovesParser().parse(raw)['config']
    assert result['show_moves'][0]['newse'] == -17
    assert result['sp_moves'][0]['newse'] == -17
