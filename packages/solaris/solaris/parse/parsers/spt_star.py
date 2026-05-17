from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class SPTstarItem(TypedDict):
    achievementid: int
    galaxyid: int
    id: int
    level: int
    rewardid: int
    starcnt: int


class _SPTstarData(TypedDict):
    item: list[SPTstarItem]


class SPTstarParser(BaseParser[_SPTstarData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SPTstar.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SPTstar.json'

    def parse(self, data: bytes) -> _SPTstarData:
        reader = BytesReader(data)
        result: _SPTstarData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            achievementid = reader.ReadSignedInt()
            galaxyid = reader.ReadSignedInt()
            id = reader.ReadSignedInt()
            level = reader.ReadSignedInt()
            rewardid = reader.ReadSignedInt()
            starcnt = reader.ReadSignedInt()

            item: SPTstarItem = {
                'achievementid': achievementid,
                'galaxyid': galaxyid,
                'id': id,
                'level': level,
                'rewardid': rewardid,
                'starcnt': starcnt,
            }
            result['item'].append(item)

        return result
