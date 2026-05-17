from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BraveLvItem(TypedDict):
    upreward: list[str]
    petid_newseid_5thmoveid: list[int]
    id: int
    storehouse: int


class _BraveLvData(TypedDict):
    item: list[BraveLvItem]


class BraveLvParser(BaseParser[_BraveLvData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'brave_lv.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'brave_lv.json'

    def parse(self, data: bytes) -> _BraveLvData:
        reader = BytesReader(data)
        result: _BraveLvData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item_id = reader.ReadSignedInt()
            petid_newseid_5thmoveid: list[int] = []
            if reader.ReadBoolean():
                pc = reader.ReadSignedInt()
                petid_newseid_5thmoveid = [reader.ReadSignedInt() for _ in range(pc)]
            storehouse = reader.ReadSignedInt()
            upreward: list[str] = []
            if reader.ReadBoolean():
                uc = reader.ReadSignedInt()
                upreward = [reader.ReadUTFBytesWithLength() for _ in range(uc)]

            item: BraveLvItem = {
                'upreward': upreward,
                'petid_newseid_5thmoveid': petid_newseid_5thmoveid,
                'id': item_id,
                'storehouse': storehouse,
            }
            result['item'].append(item)

        return result
