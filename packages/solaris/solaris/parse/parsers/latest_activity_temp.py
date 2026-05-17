from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class LatestActivityTempInfo(TypedDict):
    goto: str
    id: int
    page: int
    pic: int
    showEnd: str
    showStart: str
    tag: int
    type: int


class _LatestActivityTempData(TypedDict):
    item: list[LatestActivityTempInfo]


class LatestActivityTempParser(BaseParser[_LatestActivityTempData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'latestActivity_temp.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'latestActivity_temp.json'

    def parse(self, data: bytes) -> _LatestActivityTempData:
        reader = BytesReader(data)
        result: _LatestActivityTempData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: LatestActivityTempInfo = {
                'goto': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'page': reader.ReadSignedInt(),
                'pic': reader.ReadSignedInt(),
                'showEnd': reader.ReadUTFBytesWithLength(),
                'showStart': reader.ReadUTFBytesWithLength(),
                'tag': reader.ReadSignedInt(),
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
