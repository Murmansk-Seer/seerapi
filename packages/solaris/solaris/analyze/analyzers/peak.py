from datetime import datetime
from typing import TYPE_CHECKING

from seerapi_models.peak import PeakSeason
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.typing_ import AnalyzeResult
from solaris.parse.parsers.activity_time_update_config import ActivityTimeUpdateInfo

if TYPE_CHECKING:
    pass


class PeakSeasonAnalyzer(BaseDataSourceAnalyzer):
    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(unity_paths=('activityTimeUpdateConfig.json',))

    @classmethod
    def get_result_res_models(cls):
        return (PeakSeason,)

    def analyze(self):
        activity_time_update_config_data: list[ActivityTimeUpdateInfo] = self._get_data(
            'unity', 'activityTimeUpdateConfig.json'
        )['root']['item']
        season = None
        start_time: datetime | None = None
        end_time: datetime | None = None

        for item in activity_time_update_config_data:
            if item.get('id') == 1:
                season = item.get('parameters1')
                start_time = datetime.strptime(
                    item.get('beginning'), '%Y_%m_%d %H:%M:%S'
                )
                end_time = datetime.strptime(item.get('ending'), '%Y_%m_%d %H:%M:%S')
                break

        if not season:
            raise ValueError('未找到赛季编号')

        if not start_time:
            raise ValueError('未找到赛季开始时间')

        if not end_time:
            raise ValueError('未找到赛季结束时间')

        peak_season = PeakSeason(
            id=1,
            start_time=start_time,
            end_time=end_time,
        )
        return (
            AnalyzeResult(
                model=PeakSeason,
                data={1: peak_season},
            ),
        )
