from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BraveTowerItem(TypedDict):
    bigbossid: str
    bossgettext: str
    bosslist: str
    raidunlocktext: str
    rewardid: str
    rewardnum: str
    rewardtype: str
    sebossid: str
    bossgetarg: int
    id: int
    raidunlockarg: int


class _BraveTowerData(TypedDict):
    item: list[BraveTowerItem]


class BraveTowerParser(BaseParser[_BraveTowerData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'brave_tower.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'brave_tower.json'

    def parse(self, data: bytes) -> _BraveTowerData:
        reader = BytesReader(data)
        result: _BraveTowerData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: BraveTowerItem = {
                'bigbossid': reader.ReadUTFBytesWithLength(),
                'bossgetarg': reader.ReadSignedInt(),
                'bossgettext': reader.ReadUTFBytesWithLength(),
                'bosslist': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'raidunlockarg': reader.ReadSignedInt(),
                'raidunlocktext': reader.ReadUTFBytesWithLength(),
                'rewardid': reader.ReadUTFBytesWithLength(),
                'rewardnum': reader.ReadUTFBytesWithLength(),
                'rewardtype': reader.ReadUTFBytesWithLength(),
                'sebossid': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)

        return result
