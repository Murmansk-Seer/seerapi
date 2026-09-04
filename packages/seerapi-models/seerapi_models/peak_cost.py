from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship

from seerapi_models.build_model import BaseResModel, ConvertToORM
from seerapi_models.common import ResourceRef

if TYPE_CHECKING:
    from seerapi_models.pet import Pet, PetORM


class BasePeakCostPool(BaseResModel):
    cost: int = Field(description='该池的消耗')
    name: str = Field(description='该池的名称')
    start_time: datetime = Field(description='该池的开始时间')
    end_time: datetime = Field(description='该池的结束时间')

    @classmethod
    def resource_name(cls) -> str:
        return 'peak_cost_pool'


class PeakCostPool(BasePeakCostPool, ConvertToORM['PeakCostPoolORM']):
    pet: list[ResourceRef['Pet']] = Field(
        default_factory=list, description='该池内的精灵'
    )

    @classmethod
    def get_orm_model(cls) -> 'type[PeakCostPoolORM]':
        return PeakCostPoolORM

    def to_orm(self) -> 'PeakCostPoolORM':
        return PeakCostPoolORM(
            id=self.id,
            cost=self.cost,
            name=self.name,
            start_time=self.start_time,
            end_time=self.end_time,
        )


class PeakCostPoolORM(BasePeakCostPool, table=True):
    pet: list['PetORM'] = Relationship(back_populates='peak_cost_pool')
