from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class TeamTaskInfoItem(TypedDict):
    TeamTaskDescription: str
    TeamTaskName: str
    TeamTaskBaseReward: list[int]
    TeamTaskExtraReward: list[int]
    TeamTaskRecommendPets: list[int]
    id: int
    TeamTaskDispatchTime: int
    TeamTaskNeedPetNum: int
    TeamTaskStar: int


class _TeamTaskInfoData(TypedDict):
    item: list[TeamTaskInfoItem]


class TeamTaskInfoParser(BaseParser[_TeamTaskInfoData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'TeamTaskInfo.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'TeamTaskInfo.json'

    def parse(self, data: bytes) -> _TeamTaskInfoData:
        reader = BytesReader(data)
        result: _TeamTaskInfoData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            TeamTaskBaseReward: list[int] = []
            if reader.ReadBoolean():
                bc = reader.ReadSignedInt()
                TeamTaskBaseReward = [reader.ReadSignedInt() for _ in range(bc)]
            TeamTaskDescription = reader.ReadUTFBytesWithLength()
            TeamTaskDispatchTime = reader.ReadSignedInt()
            TeamTaskExtraReward: list[int] = []
            if reader.ReadBoolean():
                ec = reader.ReadSignedInt()
                TeamTaskExtraReward = [reader.ReadSignedInt() for _ in range(ec)]
            TeamTaskName = reader.ReadUTFBytesWithLength()
            TeamTaskNeedPetNum = reader.ReadSignedInt()
            TeamTaskRecommendPets: list[int] = []
            if reader.ReadBoolean():
                pc = reader.ReadSignedInt()
                TeamTaskRecommendPets = [reader.ReadSignedInt() for _ in range(pc)]
            TeamTaskStar = reader.ReadSignedInt()
            item_id = reader.ReadSignedInt()

            item: TeamTaskInfoItem = {
                'TeamTaskDescription': TeamTaskDescription,
                'TeamTaskName': TeamTaskName,
                'TeamTaskBaseReward': TeamTaskBaseReward,
                'TeamTaskExtraReward': TeamTaskExtraReward,
                'TeamTaskRecommendPets': TeamTaskRecommendPets,
                'id': item_id,
                'TeamTaskDispatchTime': TeamTaskDispatchTime,
                'TeamTaskNeedPetNum': TeamTaskNeedPetNum,
                'TeamTaskStar': TeamTaskStar,
            }
            result['item'].append(item)

        return result
