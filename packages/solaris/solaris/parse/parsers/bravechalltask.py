from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BravechalltaskItem(TypedDict):
    jump: str
    NewMsglogId: str
    rewardinfo: str
    taskparam: str
    title: str
    value: str
    group: int
    id: int
    init: int
    num: int
    tasktype: int


class _BravechalltaskData(TypedDict):
    item: list[BravechalltaskItem]


class BravechalltaskParser(BaseParser[_BravechalltaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'Bravechalltask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'Bravechalltask.json'

    def parse(self, data: bytes) -> _BravechalltaskData:
        reader = BytesReader(data)
        result: _BravechalltaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: BravechalltaskItem = {
                'NewMsglogId': reader.ReadUTFBytesWithLength(),
                'group': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'init': reader.ReadSignedInt(),
                'jump': reader.ReadUTFBytesWithLength(),
                'num': reader.ReadSignedInt(),
                'rewardinfo': reader.ReadUTFBytesWithLength(),
                'taskparam': reader.ReadUTFBytesWithLength(),
                'tasktype': reader.ReadSignedInt(),
                'title': reader.ReadUTFBytesWithLength(),
                'value': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)

        return result
