from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from seerapi_models import Skill, SkillStone, SkillStoneEffect

SKILL_STONE_ATTACK_CATEGORY_NAMES = {
    1: '物理',
    2: '特殊',
    4: '属性',
}
SKILL_STONE_RUNTIME_CATEGORY_FACTOR = 100_000
SKILL_STONE_RUNTIME_EFFECT_FACTOR = 1_000


@dataclass(frozen=True, slots=True)
class SkillStoneRuntimeId:
    runtime_id: int
    attack_category_id: int
    attack_category_name: str
    effect_inner_id: int
    stone_id: int


@dataclass(frozen=True, slots=True)
class ResolvedRuntimeSkill:
    runtime_id: int
    kind: Literal['skill', 'skill_stone']
    skill: Skill | None = None
    skill_stone: SkillStone | None = None
    skill_stone_runtime: SkillStoneRuntimeId | None = None
    selected_effect: SkillStoneEffect | None = None

    def model_dump(self) -> dict[str, object]:
        data: dict[str, object] = {
            'runtime_id': self.runtime_id,
            'kind': self.kind,
        }
        if self.skill is not None:
            data['skill'] = self.skill.model_dump(mode='json')
        if self.skill_stone is not None:
            data['skill_stone'] = self.skill_stone.model_dump(mode='json')
        if self.skill_stone_runtime is not None:
            data['skill_stone_runtime'] = {
                'attack_category_id': self.skill_stone_runtime.attack_category_id,
                'attack_category_name': self.skill_stone_runtime.attack_category_name,
                'effect_inner_id': self.skill_stone_runtime.effect_inner_id,
                'stone_id': self.skill_stone_runtime.stone_id,
            }
        if self.selected_effect is not None:
            data['selected_effect'] = self.selected_effect.model_dump(mode='json')
        return data


def decode_skill_stone_runtime_id(skill_id: int) -> SkillStoneRuntimeId | None:
    """Decode the category/effect/stone segments used in lineup skill slots."""

    if skill_id <= SKILL_STONE_RUNTIME_CATEGORY_FACTOR:
        return None
    attack_category_id = skill_id // SKILL_STONE_RUNTIME_CATEGORY_FACTOR
    attack_category_name = SKILL_STONE_ATTACK_CATEGORY_NAMES.get(attack_category_id)
    if attack_category_name is None:
        return None
    remainder = skill_id % SKILL_STONE_RUNTIME_CATEGORY_FACTOR
    stone_id = remainder % SKILL_STONE_RUNTIME_EFFECT_FACTOR
    if stone_id <= 0:
        return None
    return SkillStoneRuntimeId(
        runtime_id=skill_id,
        attack_category_id=attack_category_id,
        attack_category_name=attack_category_name,
        effect_inner_id=remainder // SKILL_STONE_RUNTIME_EFFECT_FACTOR,
        stone_id=stone_id,
    )


__all__ = [
    'SKILL_STONE_ATTACK_CATEGORY_NAMES',
    'ResolvedRuntimeSkill',
    'SkillStoneRuntimeId',
    'decode_skill_stone_runtime_id',
]
