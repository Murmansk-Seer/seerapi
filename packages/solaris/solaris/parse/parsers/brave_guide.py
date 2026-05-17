from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BraveGuideItem(TypedDict):
    guideparam: list[str]
    guidetype: int
    id: int


class _BraveGuideData(TypedDict):
    item: list[BraveGuideItem]


class BraveGuideParser(BaseParser[_BraveGuideData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'brave_guide.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'brave_guide.json'

    def parse(self, data: bytes) -> _BraveGuideData:
        reader = BytesReader(data)
        result: _BraveGuideData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            guideparam: list[str] = []
            if reader.ReadBoolean():
                gc = reader.ReadSignedInt()
                guideparam = [reader.ReadUTFBytesWithLength() for _ in range(gc)]
            guidetype = reader.ReadSignedInt()
            item_id = reader.ReadSignedInt()

            item: BraveGuideItem = {
                'guideparam': guideparam,
                'guidetype': guidetype,
                'id': item_id,
            }
            result['item'].append(item)

        return result
