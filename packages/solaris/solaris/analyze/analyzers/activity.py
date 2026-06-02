from datetime import datetime
from typing import TYPE_CHECKING

from seerapi_models.activity import Activity, ActivityType
from seerapi_models.common import ResourceRef

from ..base import AnalyzeResult, BaseDataSourceAnalyzer, DataImportConfig

if TYPE_CHECKING:
    from solaris.parse.parsers.activity_center import ActivityCenterInfo


class ActivityAnalyzer(BaseDataSourceAnalyzer):
    @classmethod
    def get_data_import_config(cls) -> 'DataImportConfig':
        return DataImportConfig(unity_paths=('ActivityCenter.json',))

    @classmethod
    def get_result_res_models(cls):
        return (Activity, ActivityType)

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        activity_center_info: list['ActivityCenterInfo'] = self._get_data(
            'unity', 'ActivityCenter.json'
        )['item']
        result: dict[int, Activity] = {}
        type_map: dict[int, ActivityType] = {}
        for item in activity_center_info:
            id_ = item['id']
            start_time = None
            if beginning := item['beginning']:  # 2024_07_19 00:00:00
                start_time = datetime.strptime(beginning, '%Y_%m_%d %H:%M:%S')

            end_time = None
            if ending := item['ending']:
                end_time = datetime.strptime(ending, '%Y_%m_%d %H:%M:%S')

            type_id = item['type']
            if type_id not in type_map:
                type_map[type_id] = ActivityType(id=type_id)

            type_ref = ResourceRef.from_model(ActivityType, id=type_id)
            activity = Activity(
                id=id_,
                name=item['labelName'],
                start_time=start_time,
                end_time=end_time,
                is_show=bool(item['isShow']),
                sort_order=item['sorting'],
                type=type_ref,
            )

            result[id_] = activity
            type_map[type_id].activity.append(ResourceRef.from_model(activity))
        return (
            AnalyzeResult(Activity, result),
            AnalyzeResult(ActivityType, type_map),
        )
