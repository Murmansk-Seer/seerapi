from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class SPTrewardItem(TypedDict):
    id: int
    rewardcnt: list[int]
    rewardid: list[int]


class _SPTrewardData(TypedDict):
    item: list[SPTrewardItem]


class SPTrewardParser(BaseParser[_SPTrewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SPTreward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SPTreward.json'

    def parse(self, data: bytes) -> _SPTrewardData:
        reader = BytesReader(data)
        result: _SPTrewardData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            id = reader.ReadSignedInt()

            rewardcnt: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                rewardcnt = [reader.ReadSignedInt() for _ in range(num)]

            rewardid: list[int] = []
            if reader.ReadBoolean():
                num2 = reader.ReadSignedInt()
                rewardid = [reader.ReadSignedInt() for _ in range(num2)]

            item: SPTrewardItem = {
                'id': id,
                'rewardcnt': rewardcnt,
                'rewardid': rewardid,
            }
            result['item'].append(item)

        return result
