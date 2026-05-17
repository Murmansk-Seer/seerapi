from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class DailytaskGiftItem(TypedDict):
    NewStatLog: int
    activity: int
    diamond: int
    icon: int
    id: int
    name: str
    rewardinfo: str
    type: int


class _DailytaskGiftData(TypedDict):
    item: list[DailytaskGiftItem]


class DailytaskGiftParser(BaseParser[_DailytaskGiftData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dailytask_gift.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dailytask_gift.json'

    def parse(self, data: bytes) -> _DailytaskGiftData:
        reader = BytesReader(data)
        result: _DailytaskGiftData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            NewStatLog = reader.ReadSignedInt()
            activity = reader.ReadSignedInt()
            diamond = reader.ReadSignedInt()
            icon = reader.ReadSignedInt()
            id = reader.ReadSignedInt()
            name = reader.ReadUTFBytesWithLength()
            rewardinfo = reader.ReadUTFBytesWithLength()
            type = reader.ReadSignedInt()

            item: DailytaskGiftItem = {
                'NewStatLog': NewStatLog,
                'activity': activity,
                'diamond': diamond,
                'icon': icon,
                'id': id,
                'name': name,
                'rewardinfo': rewardinfo,
                'type': type,
            }
            result['item'].append(item)

        return result
