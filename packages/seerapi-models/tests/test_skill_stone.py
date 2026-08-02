import pytest

from seerapi_models.common import ResourceRef
from seerapi_models.element_type import TypeCombination
from seerapi_models.items import (
    Item,
    SkillStone,
    SkillStoneCategory,
    SkillStoneEffect,
)


@pytest.mark.filterwarnings(
    "ignore:relationship 'SkillORM.friend_skill_effect'.*:sqlalchemy.exc.SAWarning"
)
def test_skill_stone_orm_preserves_unity_name_and_unknown_probability() -> None:
    category = SkillStoneCategory(
        id=5,
        name='电系技能石',
        skill_stone=[],
        type=ResourceRef.from_model(TypeCombination, id=5),
    )
    stone = SkillStone(
        id=25,
        name='S级电系技能石',
        move_name='电石之力-S',
        rank=5,
        power=160,
        max_pp=2,
        accuracy=100,
        category=ResourceRef.from_model(category),
        item=ResourceRef.from_model(Item, id=1_100_025),
        effect=[SkillStoneEffect(inner_id=5, prob=None, effect=[])],
    )

    orm = stone.to_orm()

    assert orm.move_name == '电石之力-S'
    assert orm.effect[0].inner_id == 5
    assert orm.effect[0].prob is None
