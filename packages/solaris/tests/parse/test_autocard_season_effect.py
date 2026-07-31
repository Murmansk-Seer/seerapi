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
            _text('每个商店阶段前3次购买价格减少1枚金币'),
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
                name='霁天',
                unlock_round=5,
                stage=1,
            ),
            _row(
                effect_id=13,
                name='湍泷',
                unlock_round=10,
                stage=2,
            ),
        )
    )

    parsed = AutocardSeasonEffectParser().parse(payload)

    assert parsed['data'] == [
        {
            'count_buff_id': '50044',
            'buff_id': '50044',
            'buff_param': '3_1',
            'count_type': 1,
            'count_num': 3,
            'sanctuary_id': 2,
            'name': '霁天',
            'description': '每个商店阶段前3次购买价格减少1枚金币',
            'id': 10,
            'unlock_round': 5,
            'pic_id': 0,
            'season_id': 1,
            'stage': 1,
        },
        {
            'count_buff_id': '50044',
            'buff_id': '50044',
            'buff_param': '3_1',
            'count_type': 1,
            'count_num': 3,
            'sanctuary_id': 2,
            'name': '湍泷',
            'description': '每个商店阶段前3次购买价格减少1枚金币',
            'id': 13,
            'unlock_round': 10,
            'pic_id': 0,
            'season_id': 1,
            'stage': 2,
        },
    ]


def test_parse_disabled_autocard_season_effect_table() -> None:
    assert AutocardSeasonEffectParser().parse(b'\x00') == {'data': []}
