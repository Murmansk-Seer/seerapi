from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BattlepassRewardItem(TypedDict):
    freereward: str
    paidreward: str
    diamondnum: int
    exp: int
    id: int


class _BattlepassRewardData(TypedDict):
    item: list[BattlepassRewardItem]


class BattlepassRewardParser(BaseParser[_BattlepassRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'battlepass_reward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'battlepass_reward.json'

    def parse(self, data: bytes) -> _BattlepassRewardData:
        reader = BytesReader(data)
        result: _BattlepassRewardData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: BattlepassRewardItem = {
                'diamondnum': reader.ReadSignedInt(),
                'exp': reader.ReadSignedInt(),
                'freereward': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'paidreward': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)

        return result
