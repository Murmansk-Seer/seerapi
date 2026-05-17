from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class LoginGiftItem(TypedDict):
    drop_list: str
    id: int


class _LoginGiftData(TypedDict):
    item: list[LoginGiftItem]


class LoginGiftParser(BaseParser[_LoginGiftData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'LoginGift.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'LoginGift.json'

    def parse(self, data: bytes) -> _LoginGiftData:
        reader = BytesReader(data)
        result: _LoginGiftData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            drop_list = reader.ReadUTFBytesWithLength()
            id = reader.ReadSignedInt()

            item: LoginGiftItem = {
                'drop_list': drop_list,
                'id': id,
            }
            result['item'].append(item)

        return result
