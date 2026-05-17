from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class SixthousandReturnSignItem(TypedDict):
    id: int
    newreward1: str
    newreward2: str
    newreward3: str
    oldreward: str


class _SixthousandReturnSignData(TypedDict):
    item: list[SixthousandReturnSignItem]


class SixthousandReturnSignParser(BaseParser[_SixthousandReturnSignData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'sixthousandReturnSign.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'sixthousandReturnSign.json'

    def parse(self, data: bytes) -> _SixthousandReturnSignData:
        reader = BytesReader(data)
        result: _SixthousandReturnSignData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            id = reader.ReadSignedInt()
            newreward1 = reader.ReadUTFBytesWithLength()
            newreward2 = reader.ReadUTFBytesWithLength()
            newreward3 = reader.ReadUTFBytesWithLength()
            oldreward = reader.ReadUTFBytesWithLength()

            item: SixthousandReturnSignItem = {
                'id': id,
                'newreward1': newreward1,
                'newreward2': newreward2,
                'newreward3': newreward3,
                'oldreward': oldreward,
            }
            result['item'].append(item)

        return result
