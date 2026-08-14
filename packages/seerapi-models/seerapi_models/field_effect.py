from sqlmodel import Field, Relationship

from seerapi_models.build_model import BaseCategoryModel, ConvertToORM
from seerapi_models.common import BaseResModel, ResourceRef


class BaseFieldEffect(BaseResModel):
    name: str = Field(description='效果名称')
    desc: str = Field(description='效果描述')

    @classmethod
    def resource_name(cls) -> str:
        return 'field_effect'


class FieldEffect(BaseFieldEffect, ConvertToORM['FieldEffectORM']):
    type: ResourceRef['FieldEffectType'] = Field(description='效果类型')

    @classmethod
    def get_orm_model(cls) -> 'type[FieldEffectORM]':
        return FieldEffectORM

    def to_orm(self) -> 'FieldEffectORM':
        return FieldEffectORM(
            id=self.id,
            name=self.name,
            desc=self.desc,
            type_id=self.type.id,
        )


class FieldEffectORM(BaseFieldEffect, table=True):
    type_id: int = Field(foreign_key='field_effect_type.id')
    type: 'FieldEffectTypeORM' = Relationship(back_populates='effect')


class BaseFieldEffectType(BaseCategoryModel):
    @classmethod
    def resource_name(cls) -> str:
        return 'field_effect_type'


class FieldEffectType(BaseFieldEffectType, ConvertToORM['FieldEffectTypeORM']):
    effect: list[ResourceRef['FieldEffect']] = Field(description='效果列表')

    @classmethod
    def get_orm_model(cls) -> 'type[FieldEffectTypeORM]':
        return FieldEffectTypeORM

    def to_orm(self) -> 'FieldEffectTypeORM':
        return FieldEffectTypeORM(id=self.id)


class FieldEffectTypeORM(BaseFieldEffectType, table=True):
    effect: list['FieldEffectORM'] = Relationship(back_populates='type')
