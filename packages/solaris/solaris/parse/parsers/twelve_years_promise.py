from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class TwelveYearsPromiseItem(TypedDict):
    BGM: str
    answer: str
    bg: int
    bgEffect: int
    chapter: int
    deal: str
    dir: int
    groupId: int
    id: int
    itemEffect: int
    itemId: int
    mask: int
    mask2: int
    maskEffect: int
    msg: str
    npcId: int
    npcName: str
    sound: str


class _TwelveYearsPromiseData(TypedDict):
    item: list[TwelveYearsPromiseItem]


class TwelveYearsPromiseParser(BaseParser[_TwelveYearsPromiseData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'twelveYearsPromise.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'twelveYearsPromise.json'

    def parse(self, data: bytes) -> _TwelveYearsPromiseData:
        reader = BytesReader(data)
        result: _TwelveYearsPromiseData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            BGM = reader.ReadUTFBytesWithLength()
            answer = reader.ReadUTFBytesWithLength()
            bg = reader.ReadSignedInt()
            bgEffect = reader.ReadSignedInt()
            chapter = reader.ReadSignedInt()
            deal = reader.ReadUTFBytesWithLength()
            dir = reader.ReadSignedInt()
            groupId = reader.ReadSignedInt()
            id = reader.ReadSignedInt()
            itemEffect = reader.ReadSignedInt()
            itemId = reader.ReadSignedInt()
            mask = reader.ReadSignedInt()
            mask2 = reader.ReadSignedInt()
            maskEffect = reader.ReadSignedInt()
            msg = reader.ReadUTFBytesWithLength()
            npcId = reader.ReadSignedInt()
            npcName = reader.ReadUTFBytesWithLength()
            sound = reader.ReadUTFBytesWithLength()

            item: TwelveYearsPromiseItem = {
                'BGM': BGM,
                'answer': answer,
                'bg': bg,
                'bgEffect': bgEffect,
                'chapter': chapter,
                'deal': deal,
                'dir': dir,
                'groupId': groupId,
                'id': id,
                'itemEffect': itemEffect,
                'itemId': itemId,
                'mask': mask,
                'mask2': mask2,
                'maskEffect': maskEffect,
                'msg': msg,
                'npcId': npcId,
                'npcName': npcName,
                'sound': sound,
            }
            result['item'].append(item)

        return result
