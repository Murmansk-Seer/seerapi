from collections.abc import Callable
from functools import cached_property
from typing import TYPE_CHECKING, Any, cast

from seerapi_models.common import ResourceRef, SkillEffectInUse
from seerapi_models.element_type import TypeCombination
from seerapi_models.items import Item, SkillStone, SkillStoneCategory, SkillStoneEffect
from solaris.analyze.base import AnalyzeResult, DataImportConfig
from solaris.analyze.utils import CategoryMap

from ..skill import BaseSkillEffectAnalyzer
from ._general import BaseItemAnalyzer

if TYPE_CHECKING:
    from solaris.parse.parsers.items_optimize import Item11
    from solaris.parse.parsers.move_stones import MoveStoneItem


if TYPE_CHECKING:

    class SkillStoneDict(Item11):
        move_name: str
        power: int
        max_pp: int
        accuracy: int
        effect: list['SkillStoneEffect']


CreateSkillEffects = Callable[[list[int], list[int]], list[SkillEffectInUse]]


def _as_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _flash_effect_probability_map(
    flash_stone: dict[str, Any] | None,
) -> dict[int, float]:
    if flash_stone is None:
        return {}
    result: dict[int, float] = {}
    for effect in _as_list(flash_stone.get('MoveEffect')):
        inner_id = effect.get('ID')
        probability = effect.get('EffectProb')
        if isinstance(inner_id, (int, float)) and isinstance(probability, (int, float)):
            result[int(inner_id)] = float(probability) / 100
    return result


def _build_skill_stone_data(
    item_stones: list['Item11'],
    move_stones: list['MoveStoneItem'],
    flash_stones: list[dict[str, Any]],
    create_effects: CreateSkillEffects,
) -> dict[int, 'SkillStoneDict']:
    """Merge current Unity moves with item metadata and legacy probabilities."""

    item_map = {stone['id'] - 1100000: stone for stone in item_stones}
    flash_map = {
        int(stone['ID']): stone
        for stone in flash_stones
        if isinstance(stone.get('ID'), (int, float))
    }
    result: dict[int, SkillStoneDict] = {}
    for move_stone in move_stones:
        stone_id = move_stone['id']
        try:
            item_stone = item_map[stone_id]
        except KeyError as error:
            raise ValueError(
                f'Unity skill stone {stone_id} has no matching item resource'
            ) from error

        probability_map = _flash_effect_probability_map(flash_map.get(stone_id))
        effects = [
            SkillStoneEffect(
                inner_id=effect['id'],
                prob=probability_map.get(effect['id']),
                effect=create_effects(
                    effect['side_effect'] or [],
                    effect['side_effect_arg'] or [],
                ),
            )
            for effect in move_stone['move_effect']
        ]
        result[stone_id] = {
            **item_stone,
            'move_name': move_stone['name'],
            'power': move_stone['power'],
            'max_pp': move_stone['max_pp'],
            'accuracy': move_stone['accuracy'],
            'type': move_stone['type'],
            'effect': effects,
        }
    return result


class SkillStoneAnalyzer(BaseSkillEffectAnalyzer, BaseItemAnalyzer):
    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        config = DataImportConfig(
            unity_paths=('moveStones.json',),
            flash_paths=('config.xml.SkillXMLInfo_skillStoneClass.xml',),
        )
        return (
            config
            + BaseItemAnalyzer.get_data_import_config()
            + BaseSkillEffectAnalyzer.get_data_import_config()
        )

    @classmethod
    def get_result_res_models(cls):
        return (SkillStone, SkillStoneCategory)

    @cached_property
    def skill_stone_data(self) -> dict[int, 'SkillStoneDict']:
        item_stones = cast(list['Item11'], self.get_category_items(11)['root']['items'])
        move_stones = cast(
            list['MoveStoneItem'],
            self._get_data('unity', 'moveStones.json')['root']['move_stone'],
        )
        raw_flash_stones = self._get_data(
            'flash', 'config.xml.SkillXMLInfo_skillStoneClass.xml'
        )['MoveStones']['MoveStone']
        flash_stones = cast(list[dict[str, Any]], _as_list(raw_flash_stones))
        return _build_skill_stone_data(
            item_stones,
            move_stones,
            flash_stones,
            lambda type_ids, args: self.create_skill_effect(type_ids, args),
        )

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        skill_stone_data = self.skill_stone_data

        category_type_set = set()
        skill_stone_map: dict[int, SkillStone] = {}
        skill_stone_category_map: CategoryMap[
            int,
            SkillStoneCategory,
            SkillStone,
        ] = CategoryMap('skill_stone')
        for id_, skill_stone in skill_stone_data.items():
            item_ref = ResourceRef.from_model(Item, id=id_ + 1100000)
            # 获取不带等级的技能石名称
            category_name = skill_stone['name'].split('级')[1]
            type_id = skill_stone['type']
            if type_id not in category_type_set:
                category_type_set.add(type_id)
                skill_stone_category_map[type_id] = SkillStoneCategory(
                    id=type_id,
                    name=category_name,
                    type=ResourceRef.from_model(TypeCombination, id=type_id),
                )

            category = skill_stone_category_map[type_id]
            skill_stone_obj = SkillStone(
                id=id_,
                name=skill_stone['name'],
                move_name=skill_stone['move_name'],
                rank=skill_stone['rank'],
                power=skill_stone['power'],
                max_pp=skill_stone['max_pp'],
                accuracy=skill_stone['accuracy'],
                item=item_ref,
                category=ResourceRef.from_model(category),
                effect=skill_stone['effect'],
            )
            category.skill_stone.append(ResourceRef.from_model(skill_stone_obj))
            skill_stone_map[id_] = skill_stone_obj

        return (
            AnalyzeResult(model=SkillStone, data=skill_stone_map),
            AnalyzeResult(model=SkillStoneCategory, data=skill_stone_category_map),
        )
