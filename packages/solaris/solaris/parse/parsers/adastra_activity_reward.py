from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AdastraActivityRewardInfo(TypedDict):
    condition: int
    id: int
    reward: str
    type: int


class _AdastraActivityRewardData(TypedDict):
    item: list[AdastraActivityRewardInfo]


class AdastraActivityRewardParser(BaseParser[_AdastraActivityRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AdastraActivityReward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AdastraActivityReward.json'

    def parse(self, data: bytes) -> _AdastraActivityRewardData:
        reader = BytesReader(data)
        result: _AdastraActivityRewardData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AdastraActivityRewardInfo = {
                'condition': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'reward': reader.ReadUTFBytesWithLength(),
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
