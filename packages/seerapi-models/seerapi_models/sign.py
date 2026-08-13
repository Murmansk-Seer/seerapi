from sqlmodel import Field, Relationship, SQLModel

from seerapi_models.build_model import (
    BaseResModel,
    ConvertToORM,
)

MULTIPLIER = 10000


class BaseSign(BaseResModel):
    name: str = Field(description='名称')
    desc: str | None = Field(
        default=None, description='描述，当子项描述覆盖主项描述时为null'
    )
    sort: int = Field(
        description=(
            '战斗界面印记图标的显示顺序权重，数值越小越靠前。'
            '客户端在可见性（isShow）相同时按此字段升序排列；'
            '可见图标始终优先于隐藏图标。'
        ),
    )
    is_show_num: bool = Field(description='是否显示剩余计数')
    num_des: str | None = Field(
        default=None, description='计数量词，仅在is_show_num为True时有效'
    )

    @classmethod
    def resource_name(cls) -> str:
        return 'sign'


class Sign(BaseSign, ConvertToORM['SignORM']):
    subitem: dict[int, 'SignSubitem'] = Field(
        default_factory=dict, description='子项，key为子项内部ID，value为子项对象'
    )

    @classmethod
    def get_orm_model(cls) -> 'type[SignORM]':
        return SignORM

    def to_orm(self) -> 'SignORM':
        return SignORM(
            id=self.id,
            name=self.name,
            desc=self.desc,
            sort=self.sort,
            is_show_num=self.is_show_num,
            num_des=self.num_des,
            subitem=[
                SignSubitemORM(
                    id=self.id * MULTIPLIER + subitem.subitem_id,
                    subitem_id=subitem.subitem_id,
                    icon_subid=subitem.icon_subid,
                    name=subitem.name,
                    desc=subitem.desc,
                    sign_id=self.id,
                )
                for subitem in self.subitem.values()
            ],
        )


class SignORM(BaseSign, table=True):
    subitem: list['SignSubitemORM'] = Relationship(back_populates='sign')


class SignSubitem(SQLModel):
    subitem_id: int = Field(description='子项ID')
    name: str | None = Field(default=None, description='名称，为null时使用主项名称')
    desc: str | None = Field(default=None, description='描述，为null时使用主项描述')
    icon_subid: int | None = Field(
        default=None, description='图标子ID，为null时使用不带子项ID后缀的图标'
    )


class SignSubitemORM(SignSubitem, table=True):
    __tablename__ = 'sign_subitem'  # type: ignore
    id: int = Field(primary_key=True, description='全局子项ID')
    sign_id: int = Field(foreign_key='sign.id')
    sign: 'SignORM' = Relationship(back_populates='subitem')
