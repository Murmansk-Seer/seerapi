from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class MedaltaskItem(TypedDict):
    describe: str
    jump: list[str]
    value: str
    rewardinfo: list[int]
    id: int
    target: int


class _MedaltaskData(TypedDict):
    item: list[MedaltaskItem]


class MedaltaskParser(BaseParser[_MedaltaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'medaltask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'medaltask.json'

    def parse(self, data: bytes) -> _MedaltaskData:
        reader = BytesReader(data)
        result: _MedaltaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            describe = reader.ReadUTFBytesWithLength()
            item_id = reader.ReadSignedInt()
            jump: list[str] = []
            if reader.ReadBoolean():
                jc = reader.ReadSignedInt()
                jump = [reader.ReadUTFBytesWithLength() for _ in range(jc)]
            rewardinfo: list[int] = []
            if reader.ReadBoolean():
                rc = reader.ReadSignedInt()
                rewardinfo = [reader.ReadSignedInt() for _ in range(rc)]
            target = reader.ReadSignedInt()
            value = reader.ReadUTFBytesWithLength()

            item: MedaltaskItem = {
                'describe': describe,
                'jump': jump,
                'value': value,
                'rewardinfo': rewardinfo,
                'id': item_id,
                'target': target,
            }
            result['item'].append(item)

        return result
