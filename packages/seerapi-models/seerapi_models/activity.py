from datetime import datetime

from sqlmodel import Field, Relationship

from seerapi_models.build_model import BaseCategoryModel, BaseResModel, ConvertToORM
from seerapi_models.common import ResourceRef


class BaseActivity(BaseResModel):
    name: str = Field(description='活动中文名称')
    start_time: datetime | None = Field(
        default=None, description='活动开始时间，常驻活动时为null'
    )
    end_time: datetime | None = Field(
        default=None, description='活动结束时间，常驻活动时为null'
    )
    is_show: bool = Field(description='是否显示')
    sort_order: int = Field(description='活动排序优先级')

    @classmethod
    def resource_name(cls) -> str:
        return 'activity'


class Activity(BaseActivity, ConvertToORM['ActivityORM']):
    type: ResourceRef['ActivityType'] = Field(description='活动类型')

    @classmethod
    def get_orm_model(cls) -> 'type[ActivityORM]':
        return ActivityORM

    def to_orm(self) -> 'ActivityORM':
        return ActivityORM(
            id=self.id,
            name=self.name,
            start_time=self.start_time,
            end_time=self.end_time,
            is_show=self.is_show,
            sort_order=self.sort_order,
            type_id=self.type.id,
        )


class ActivityORM(BaseActivity, table=True):
    type_id: int = Field(foreign_key='activity_type.id')
    type: 'ActivityTypeORM' = Relationship(back_populates='activity')


class BaseActivityType(BaseCategoryModel):
    @classmethod
    def resource_name(cls) -> str:
        return 'activity_type'


class ActivityType(BaseActivityType, ConvertToORM['ActivityTypeORM']):
    activity: list[ResourceRef['Activity']] = Field(
        default_factory=list, description='该分类下的所有活动'
    )

    @classmethod
    def get_orm_model(cls) -> 'type[ActivityTypeORM]':
        return ActivityTypeORM

    def to_orm(self) -> 'ActivityTypeORM':
        return ActivityTypeORM(id=self.id)


class ActivityTypeORM(BaseActivityType, table=True):
    activity: list['ActivityORM'] = Relationship(back_populates='type')
