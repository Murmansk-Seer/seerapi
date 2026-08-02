from typing import cast

import pytest

from solaris.analyze.analyzers.items.skill_stone import _build_skill_stone_data
from solaris.parse.parsers.items_optimize import Item11
from solaris.parse.parsers.move_stones import MoveStoneItem


def _item_stone(stone_id: int = 25) -> Item11:
    return cast(
        Item11,
        {
            'bean': 0,
            'id': 1_100_000 + stone_id,
            'max': 1,
            'name': 'S级电系技能石',
            'need_lv': 0,
            'rank': 5,
            'rarity': 0,
            'sort': 0,
            'type': 5,
            'cat_id': 11,
            'purpose': 0,
            'wd': 0,
        },
    )


def _move_stone(stone_id: int = 25) -> MoveStoneItem:
    return {
        'accuracy': 100,
        'id': stone_id,
        'max_pp': 2,
        'move_effect': [
            {
                'id': 5,
                'side_effect': [4],
                'side_effect_arg': [3, 15, 1],
            }
        ],
        'name': '电石之力-S',
        'power': 160,
        'type': 5,
    }


def test_skill_stone_merge_uses_unity_data_and_flash_probability() -> None:
    effect_calls: list[tuple[list[int], list[int]]] = []

    def create_effects(type_ids: list[int], args: list[int]):
        effect_calls.append((type_ids, args))
        return []

    result = _build_skill_stone_data(
        [_item_stone()],
        [_move_stone()],
        [
            {
                'ID': 25,
                'Power': 999,
                'MoveEffect': [
                    {
                        'ID': 5,
                        'EffectProb': 2,
                        'SideEffect': '999',
                        'SideEffectArg': '999',
                    }
                ],
            }
        ],
        create_effects,
    )

    stone = result[25]
    assert stone['move_name'] == '电石之力-S'
    assert stone['power'] == 160
    assert stone['max_pp'] == 2
    assert stone['accuracy'] == 100
    assert stone['effect'][0].inner_id == 5
    assert stone['effect'][0].prob == 0.02
    assert effect_calls == [([4], [3, 15, 1])]


def test_skill_stone_merge_keeps_unity_effect_when_flash_is_missing() -> None:
    result = _build_skill_stone_data(
        [_item_stone()],
        [_move_stone()],
        [],
        lambda _type_ids, _args: [],
    )

    assert result[25]['effect'][0].prob is None


def test_skill_stone_merge_rejects_a_missing_item_relation() -> None:
    with pytest.raises(ValueError, match='has no matching item resource'):
        _build_skill_stone_data(
            [],
            [_move_stone()],
            [],
            lambda _type_ids, _args: [],
        )
