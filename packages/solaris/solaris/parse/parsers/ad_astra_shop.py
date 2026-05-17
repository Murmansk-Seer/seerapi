from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AdAstraShopInfo(TypedDict):
    content: str
    costID: int
    costNum: int
    desc: str
    id: int
    limitNum: int
    limitType: int
    type: int


class _AdAstraShopData(TypedDict):
    item: list[AdAstraShopInfo]


class AdAstraShopParser(BaseParser[_AdAstraShopData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AdAstraShop.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AdAstraShop.json'

    def parse(self, data: bytes) -> _AdAstraShopData:
        reader = BytesReader(data)
        result: _AdAstraShopData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AdAstraShopInfo = {
                'content': reader.ReadUTFBytesWithLength(),
                'costID': reader.ReadSignedInt(),
                'costNum': reader.ReadSignedInt(),
                'desc': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'limitNum': reader.ReadSignedInt(),
                'limitType': reader.ReadSignedInt(),
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
