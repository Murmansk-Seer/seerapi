from sqlmodel import JSON, Field, Relationship

from seerapi_models.build_model import BaseCategoryModel, BaseResModel, ConvertToORM
from seerapi_models.common import ResourceRef


class BaseBuff(BaseResModel):
    desc: str = Field(description='效果描述')
    tag: str = Field(description='效果标签')
    desc_tag: str | None = Field(
        default=None,
        description='效果描述中的标签，用于格式化效果描述',
    )
    icon: list[int] = Field(
        default_factory=list,
        description='图标 ID 列表',
        sa_type=JSON,
    )

    @classmethod
    def resource_name(cls) -> str:
        return 'buff'


class Buff(BaseBuff, ConvertToORM['BuffORM']):
    type: ResourceRef['BuffType'] = Field(description='图标类型')

    @classmethod
    def get_orm_model(cls) -> 'type[BuffORM]':
        return BuffORM

    def to_orm(self) -> 'BuffORM':
        return BuffORM(
            id=self.id,
            desc=self.desc,
            tag=self.tag,
            desc_tag=self.desc_tag,
            icon=self.icon,
            type_id=self.type.id,
        )


class BuffORM(BaseBuff, table=True):
    type_id: int = Field(foreign_key='buff_type.id')
    type: 'BuffTypeORM' = Relationship(back_populates='buff')


class BaseBuffType(BaseCategoryModel):
    @classmethod
    def resource_name(cls) -> str:
        return 'buff_type'


class BuffType(BaseBuffType, ConvertToORM['BuffTypeORM']):
    buff: list[ResourceRef['Buff']] = Field(
        default_factory=list,
        description='Buff 列表',
    )

    @classmethod
    def get_orm_model(cls) -> 'type[BuffTypeORM]':
        return BuffTypeORM

    def to_orm(self) -> 'BuffTypeORM':
        return BuffTypeORM(id=self.id)


class BuffTypeORM(BaseBuffType, table=True):
    buff: list['BuffORM'] = Relationship(back_populates='type')
