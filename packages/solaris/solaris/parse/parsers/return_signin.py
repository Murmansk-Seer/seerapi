from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ReturnSigninItem(TypedDict):
    changereward: list[int]
    days: int
    id: int
    judgepet: list[int]
    previewreward1: list[int]
    previewreward2: list[int]
    reward: list[int]


class _ReturnSigninData(TypedDict):
    item: list[ReturnSigninItem]


class ReturnSigninParser(BaseParser[_ReturnSigninData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'return_signin.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'return_signin.json'

    def parse(self, data: bytes) -> _ReturnSigninData:
        reader = BytesReader(data)
        result: _ReturnSigninData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            changereward: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                changereward = [reader.ReadSignedInt() for _ in range(num)]

            days = reader.ReadSignedInt()
            id = reader.ReadSignedInt()

            judgepet: list[int] = []
            if reader.ReadBoolean():
                num2 = reader.ReadSignedInt()
                judgepet = [reader.ReadSignedInt() for _ in range(num2)]

            previewreward1: list[int] = []
            if reader.ReadBoolean():
                num3 = reader.ReadSignedInt()
                previewreward1 = [reader.ReadSignedInt() for _ in range(num3)]

            previewreward2: list[int] = []
            if reader.ReadBoolean():
                num4 = reader.ReadSignedInt()
                previewreward2 = [reader.ReadSignedInt() for _ in range(num4)]

            reward: list[int] = []
            if reader.ReadBoolean():
                num5 = reader.ReadSignedInt()
                reward = [reader.ReadSignedInt() for _ in range(num5)]

            item: ReturnSigninItem = {
                'changereward': changereward,
                'days': days,
                'id': id,
                'judgepet': judgepet,
                'previewreward1': previewreward1,
                'previewreward2': previewreward2,
                'reward': reward,
            }
            result['item'].append(item)

        return result
