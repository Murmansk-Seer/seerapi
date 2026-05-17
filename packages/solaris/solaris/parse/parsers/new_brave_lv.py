from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class NewBraveLvItem(TypedDict):
    stepname: list[str]
    storehouse: str
    id: int
    stepnum: int


class _NewBraveLvData(TypedDict):
    item: list[NewBraveLvItem]


class NewBraveLvParser(BaseParser[_NewBraveLvData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'newBraveLv.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'newBraveLv.json'

    def parse(self, data: bytes) -> _NewBraveLvData:
        reader = BytesReader(data)
        result: _NewBraveLvData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item_id = reader.ReadSignedInt()
            stepname: list[str] = []
            if reader.ReadBoolean():
                sc = reader.ReadSignedInt()
                stepname = [reader.ReadUTFBytesWithLength() for _ in range(sc)]
            stepnum = reader.ReadSignedInt()
            storehouse = reader.ReadUTFBytesWithLength()

            item: NewBraveLvItem = {
                'stepname': stepname,
                'storehouse': storehouse,
                'id': item_id,
                'stepnum': stepnum,
            }
            result['item'].append(item)

        return result
