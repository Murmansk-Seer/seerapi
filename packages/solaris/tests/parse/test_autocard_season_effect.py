from __future__ import annotations

import struct

from solaris.parse.parsers.autocard_season_effect import (
    AutocardSeasonEffectParser,
)


def _text(value: str) -> bytes:
    encoded = value.encode()
    return struct.pack('<H', len(encoded)) + encoded


def _row(
    *,
    effect_id: int,
    name: str,
    unlock_round: int,
    stage: int,
) -> bytes:
    return b''.join(
        (
            _text('50044'),
            _text('50044'),
            _text('3_1'),
            struct.pack('<ii', 1, 3),
            struct.pack('<i', 2),
            _text(name),
            _text('Discount the first purchase in each shop stage'),
            struct.pack(
                '<iiiii',
                effect_id,
                unlock_round,
                0,
                1,
                stage,
            ),
        )
    )


def test_parse_autocard_season_effect_rows() -> None:
    payload = b''.join(
        (
            b'\x01',
            struct.pack('<i', 2),
            _row(
                effect_id=10,
                name='Thunder',
                unlock_round=5,
                stage=1,
            ),
            _row(
                effect_id=13,
                name='Torrent',
                unlock_round=10,
                stage=2,
            ),
        )
    )

    parsed = AutocardSeasonEffectParser().parse(payload)

    assert parsed['data'] == [
        {
            'BuffDisplay': '50044',
            'BuffId': '50044',
            'BuffParam': '3_1',
            'CountNum': 1,
            'DefaultNum': 3,
            'effectGroup': 2,
            'effectName': 'Thunder',
            'effectTxt': 'Discount the first purchase in each shop stage',
            'id': 10,
            'opTurn': 5,
            'picID': 0,
            'season': 1,
            'stageLevel': 1,
        },
        {
            'BuffDisplay': '50044',
            'BuffId': '50044',
            'BuffParam': '3_1',
            'CountNum': 1,
            'DefaultNum': 3,
            'effectGroup': 2,
            'effectName': 'Torrent',
            'effectTxt': 'Discount the first purchase in each shop stage',
            'id': 13,
            'opTurn': 10,
            'picID': 0,
            'season': 1,
            'stageLevel': 2,
        },
    ]


def test_parse_disabled_autocard_season_effect_table() -> None:
    assert AutocardSeasonEffectParser().parse(b'\x00') == {'data': []}
