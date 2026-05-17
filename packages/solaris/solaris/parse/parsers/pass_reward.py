from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class PassRewardItem(TypedDict):
    freereward: str
    paidreward: str
    diamondnum: int
    exp: int
    id: int


class _PassRewardData(TypedDict):
    item: list[PassRewardItem]


class PassRewardParser(BaseParser[_PassRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'pass_reward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'pass_reward.json'

    def parse(self, data: bytes) -> _PassRewardData:
        reader = BytesReader(data)
        result: _PassRewardData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: PassRewardItem = {
                'diamondnum': reader.ReadSignedInt(),
                'exp': reader.ReadSignedInt(),
                'freereward': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'paidreward': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)

        return result
