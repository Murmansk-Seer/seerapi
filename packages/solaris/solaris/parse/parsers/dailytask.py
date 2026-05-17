from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class DailytaskItem(TypedDict):
    describe: str
    id: int
    rewardinfo: str
    target: int
    time: int
    title: str
    value: str


class _DailytaskData(TypedDict):
    item: list[DailytaskItem]


class DailytaskParser(BaseParser[_DailytaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dailytask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dailytask.json'

    def parse(self, data: bytes) -> _DailytaskData:
        reader = BytesReader(data)
        result: _DailytaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            describe = reader.ReadUTFBytesWithLength()
            id = reader.ReadSignedInt()
            rewardinfo = reader.ReadUTFBytesWithLength()
            target = reader.ReadSignedInt()
            time = reader.ReadSignedInt()
            title = reader.ReadUTFBytesWithLength()
            value = reader.ReadUTFBytesWithLength()

            item: DailytaskItem = {
                'describe': describe,
                'id': id,
                'rewardinfo': rewardinfo,
                'target': target,
                'time': time,
                'title': title,
                'value': value,
            }
            result['item'].append(item)

        return result
