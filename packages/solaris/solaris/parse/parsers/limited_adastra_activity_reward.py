from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class LimitedAdastraActivityRewardInfo(TypedDict):
    condition: int
    endTime: str
    id: int
    reward: str
    type: int
    unlockTime: str


class _LimitedAdastraActivityRewardData(TypedDict):
    item: list[LimitedAdastraActivityRewardInfo]


class LimitedAdastraActivityRewardParser(BaseParser[_LimitedAdastraActivityRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'LimitedAdastraActivityReward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'LimitedAdastraActivityReward.json'

    def parse(self, data: bytes) -> _LimitedAdastraActivityRewardData:
        reader = BytesReader(data)
        result: _LimitedAdastraActivityRewardData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: LimitedAdastraActivityRewardInfo = {
                'condition': reader.ReadSignedInt(),
                'endTime': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'reward': reader.ReadUTFBytesWithLength(),
                'type': reader.ReadSignedInt(),
                'unlockTime': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)
        return result
