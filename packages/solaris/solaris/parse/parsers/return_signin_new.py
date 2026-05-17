from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ReturnSigninNewItem(TypedDict):
    days: int
    fiexdreward1: list[int]
    fiexdreward2: list[int]
    id: int
    intro1: str
    intro2: str
    judgepet: list[int]
    jump1: int
    jump2: int
    name1: str
    name2: str
    optreward1: list[int]
    optreward2: list[int]


class _ReturnSigninNewData(TypedDict):
    item: list[ReturnSigninNewItem]


class ReturnSigninNewParser(BaseParser[_ReturnSigninNewData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'return_signin_new.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'return_signin_new.json'

    def parse(self, data: bytes) -> _ReturnSigninNewData:
        reader = BytesReader(data)
        result: _ReturnSigninNewData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            days = reader.ReadSignedInt()

            fiexdreward1: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                fiexdreward1 = [reader.ReadSignedInt() for _ in range(num)]

            fiexdreward2: list[int] = []
            if reader.ReadBoolean():
                num2 = reader.ReadSignedInt()
                fiexdreward2 = [reader.ReadSignedInt() for _ in range(num2)]

            id = reader.ReadSignedInt()
            intro1 = reader.ReadUTFBytesWithLength()
            intro2 = reader.ReadUTFBytesWithLength()

            judgepet: list[int] = []
            if reader.ReadBoolean():
                num3 = reader.ReadSignedInt()
                judgepet = [reader.ReadSignedInt() for _ in range(num3)]

            jump1 = reader.ReadSignedInt()
            jump2 = reader.ReadSignedInt()
            name1 = reader.ReadUTFBytesWithLength()
            name2 = reader.ReadUTFBytesWithLength()

            optreward1: list[int] = []
            if reader.ReadBoolean():
                num4 = reader.ReadSignedInt()
                optreward1 = [reader.ReadSignedInt() for _ in range(num4)]

            optreward2: list[int] = []
            if reader.ReadBoolean():
                num5 = reader.ReadSignedInt()
                optreward2 = [reader.ReadSignedInt() for _ in range(num5)]

            item: ReturnSigninNewItem = {
                'days': days,
                'fiexdreward1': fiexdreward1,
                'fiexdreward2': fiexdreward2,
                'id': id,
                'intro1': intro1,
                'intro2': intro2,
                'judgepet': judgepet,
                'jump1': jump1,
                'jump2': jump2,
                'name1': name1,
                'name2': name2,
                'optreward1': optreward1,
                'optreward2': optreward2,
            }
            result['item'].append(item)

        return result
