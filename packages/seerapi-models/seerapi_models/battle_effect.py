from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from seerapi_models.build_model import BaseCategoryModel, BaseResModel, ConvertToORM
from seerapi_models.common import ResourceRef


class BattleEffectCategoryLink(SQLModel, table=True):
    battle_effect_id: int | None = Field(
        default=None, foreign_key='battle_effect.id', primary_key=True
    )
    type_id: int | None = Field(
        default=None, foreign_key='battle_effect_type.id', primary_key=True
    )


class BattleEffectBase(BaseResModel):
    name: str = Field(description='状态名称')
    desc: str = Field(description='状态描述')

    @classmethod
    def resource_name(cls) -> str:
        return 'battle_effect'


class BattleEffect(BattleEffectBase, ConvertToORM['BattleEffectORM']):
    type: list[ResourceRef['BattleEffectCategory']] = Field(
        default_factory=list,
        description='状态类型，可能同时属于多个类型，例如瘫痪同时属于控制类和限制类异常',
    )
    resistance: ResourceRef['ResistanceCategory'] | None = Field(
        default=None,
        description='抗性类型',
    )

    @classmethod
    def get_orm_model(cls) -> 'type[BattleEffectORM]':
        return BattleEffectORM

    def to_orm(self) -> 'BattleEffectORM':
        return BattleEffectORM(
            id=self.id,
            name=self.name,
            desc=self.desc,
            resistance_id=self.resistance.id if self.resistance is not None else None,
        )


class BattleEffectORM(BattleEffectBase, table=True):
    type: list['BattleEffectCategoryORM'] = Relationship(
        back_populates='effect', link_model=BattleEffectCategoryLink
    )
    resistance_id: int | None = Field(
        default=None, foreign_key='resistance_category.id'
    )
    resistance: Optional['ResistanceCategoryORM'] = Relationship(
        back_populates='effect'
    )


class BattleEffectCategoryBase(BaseCategoryModel):
    name: str = Field(description='状态类型名称')

    @classmethod
    def resource_name(cls) -> str:
        return 'battle_effect_type'


class BattleEffectCategory(
    BattleEffectCategoryBase, ConvertToORM['BattleEffectCategoryORM']
):
    effect: list[ResourceRef['BattleEffect']] = Field(
        default_factory=list, description='异常状态列表'
    )

    @classmethod
    def get_orm_model(cls) -> type['BattleEffectCategoryORM']:
        return BattleEffectCategoryORM

    def to_orm(self) -> 'BattleEffectCategoryORM':
        return BattleEffectCategoryORM(
            id=self.id,
            name=self.name,
        )


class BattleEffectCategoryORM(BattleEffectCategoryBase, table=True):
    effect: list['BattleEffectORM'] = Relationship(
        back_populates='type', link_model=BattleEffectCategoryLink
    )


class BaseResistanceCategory(BaseCategoryModel):
    name: str = Field(description='抗性类型名称')

    @classmethod
    def resource_name(cls) -> str:
        return 'resistance_category'


class ResistanceCategory(
    BaseResistanceCategory,
    ConvertToORM['ResistanceCategoryORM'],
):
    effect: list[ResourceRef['BattleEffect']] = Field(
        default_factory=list, description='异常状态列表'
    )

    @classmethod
    def get_orm_model(cls) -> type['ResistanceCategoryORM']:
        return ResistanceCategoryORM

    def to_orm(self) -> 'ResistanceCategoryORM':
        return ResistanceCategoryORM(
            id=self.id,
            name=self.name,
        )


class ResistanceCategoryORM(BaseResistanceCategory, table=True):
    effect: list['BattleEffectORM'] = Relationship(back_populates='resistance')
