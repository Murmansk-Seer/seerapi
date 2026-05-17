from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class LatestActivityInfo(TypedDict):
    goto: list[str]
    id: int
    page: int
    pic: int
    showEnd: str
    showStart: str
    tag: int
    type: int


class _LatestActivityData(TypedDict):
    item: list[LatestActivityInfo]


class LatestActivityParser(BaseParser[_LatestActivityData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'latestActivity.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'latestActivity.json'

    def parse(self, data: bytes) -> _LatestActivityData:
        reader = BytesReader(data)
        result: _LatestActivityData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            goto: list[str] = []
            if reader.ReadBoolean():
                gc = reader.ReadSignedInt()
                goto = [reader.ReadUTFBytesWithLength() for _ in range(gc)]
            id_val = reader.ReadSignedInt()
            page = reader.ReadSignedInt()
            pic = reader.ReadSignedInt()
            show_end = reader.ReadUTFBytesWithLength()
            show_start = reader.ReadUTFBytesWithLength()
            tag = reader.ReadSignedInt()
            type_val = reader.ReadSignedInt()
            item: LatestActivityInfo = {
                'goto': goto,
                'id': id_val,
                'page': page,
                'pic': pic,
                'showEnd': show_end,
                'showStart': show_start,
                'tag': tag,
                'type': type_val,
            }
            result['item'].append(item)
        return result
