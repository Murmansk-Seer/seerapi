from datetime import datetime
from typing import TYPE_CHECKING

from seerapi_models.common import ResourceRef
from seerapi_models.peak_cost import PeakCostPool
from seerapi_models.pet import Pet
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.typing_ import AnalyzeResult
from solaris.utils import CN_TZ

if TYPE_CHECKING:
    from solaris.parse.parsers.pvp_cost_mode_cost import PvpCostModeCostConfig


def parse_end_datetime(time_str: str) -> datetime:
    """将 ``YYYY_MM_DD HH:MM:SS`` 格式的时间转换为 datetime。"""
    return datetime.strptime(time_str, '%Y_%m_%d %H:%M:%S').replace(tzinfo=CN_TZ)


def parse_start_time(time_str: str) -> datetime:
    time_str = time_str[2:]
    time = datetime.strptime(time_str, '%Y%m%d')
    return time.replace(hour=10, tzinfo=CN_TZ)


class PeakCostAnalyzer(BaseDataSourceAnalyzer):
    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(
            unity_paths=(
                'pvpCostMode_cost.json',
                # 'pvpCostMode_vote.json',
                # 'pvpCostMode_votePrice.json',
            )
        )

    @classmethod
    def get_result_res_models(cls):
        return (PeakCostPool,)

    def analyze(self):
        pvp_cost_data: PvpCostModeCostConfig = self._get_data(
            'unity', 'pvpCostMode_cost.json'
        )
        pool_map: dict[int, PeakCostPool] = {}

        for item in pvp_cost_data['item']:
            cost = item['cost']
            if cost == 0:
                continue

            start_time = parse_start_time(str(item['subkeyMonth']))
            peak_pool = PeakCostPool(
                id=cost,
                cost=cost,
                name=item['name'],
                start_time=start_time,
                end_time=parse_end_datetime(item['time']),
                pet=[
                    ResourceRef.from_model(Pet, id=int(pet_id))
                    for pet_id in filter(None, item['pet'].split(';'))
                ],
            )
            pool_map[cost] = peak_pool

        return (AnalyzeResult(model=PeakCostPool, data=pool_map),)
