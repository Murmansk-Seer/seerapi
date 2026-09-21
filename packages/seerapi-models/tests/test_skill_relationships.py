from sqlalchemy.orm import configure_mappers

from seerapi_models.common import SkillEffectInUseORM
from seerapi_models.skill import SkillORM


def _skill() -> SkillORM:
    return SkillORM(
        id=1,
        name='测试技能',
        power=0,
        max_pp=1,
        accuracy=100,
        crit_rate=None,
        priority=0,
        must_hit=True,
        category_id=1,
        type_id=1,
    )


def _effect() -> SkillEffectInUseORM:
    return SkillEffectInUseORM(
        info='测试效果',
        analyze_info='测试效果',
        args=[],
        effect_id=1,
    )


def test_friend_skill_effect_is_bidirectional() -> None:
    configure_mappers()
    skill = _skill()
    effect = _effect()

    skill.friend_skill_effect.append(effect)

    assert skill.friend_skill_effect == [effect]
    assert effect.friend_skill == [skill]

    skill.friend_skill_effect.remove(effect)

    assert skill.friend_skill_effect == []
    assert effect.friend_skill == []


def test_regular_skill_effect_uses_independent_relationship() -> None:
    skill = _skill()
    effect = _effect()

    skill.skill_effect.append(effect)

    assert skill.skill_effect == [effect]
    assert effect.skill == [skill]
    assert skill.friend_skill_effect == []
    assert effect.friend_skill == []
