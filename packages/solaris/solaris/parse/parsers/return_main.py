from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ReturnMainItem(TypedDict):
    id: int
    level: int
    onespet: list[int]
    onesreward: list[int]
    previewitem: list[int]
    previewpet: list[int]


class _ReturnMainData(TypedDict):
    item: list[ReturnMainItem]


class ReturnMainParser(BaseParser[_ReturnMainData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'return_main.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'return_main.json'

    def parse(self, data: bytes) -> _ReturnMainData:
        reader = BytesReader(data)
        result: _ReturnMainData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            id = reader.ReadSignedInt()
            level = reader.ReadSignedInt()

            onespet: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                onespet = [reader.ReadSignedInt() for _ in range(num)]

            onesreward: list[int] = []
            if reader.ReadBoolean():
                num2 = reader.ReadSignedInt()
                onesreward = [reader.ReadSignedInt() for _ in range(num2)]

            previewitem: list[int] = []
            if reader.ReadBoolean():
                num3 = reader.ReadSignedInt()
                previewitem = [reader.ReadSignedInt() for _ in range(num3)]

            previewpet: list[int] = []
            if reader.ReadBoolean():
                num4 = reader.ReadSignedInt()
                previewpet = [reader.ReadSignedInt() for _ in range(num4)]

            item: ReturnMainItem = {
                'id': id,
                'level': level,
                'onespet': onespet,
                'onesreward': onesreward,
                'previewitem': previewitem,
                'previewpet': previewpet,
            }
            result['item'].append(item)

        return result
