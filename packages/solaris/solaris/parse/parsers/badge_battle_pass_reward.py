from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BadgeBattlePassRewardItem(TypedDict):
    freereward: str
    paidreward: str
    diamondnum: int
    exp: int
    id: int


class _BadgeBattlePassRewardData(TypedDict):
    item: list[BadgeBattlePassRewardItem]


class BadgeBattlePassRewardParser(BaseParser[_BadgeBattlePassRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'badgeBattlePass_reward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'badgeBattlePass_reward.json'

    def parse(self, data: bytes) -> _BadgeBattlePassRewardData:
        reader = BytesReader(data)
        result: _BadgeBattlePassRewardData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: BadgeBattlePassRewardItem = {
                'diamondnum': reader.ReadSignedInt(),
                'exp': reader.ReadSignedInt(),
                'freereward': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'paidreward': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)

        return result
