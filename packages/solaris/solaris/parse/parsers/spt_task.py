from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class SPTtaskItem(TypedDict):
    btlconid: list[int]
    firstreward: list[int]
    galaxyid: int
    id: int
    isend: int
    monsterid: list[int]
    otherreward: str
    taskmode: int
    taskstep: int
    tasktype: int
    unlockcond: list[int]
    unlockmark: int


class _SPTtaskData(TypedDict):
    item: list[SPTtaskItem]


class SPTtaskParser(BaseParser[_SPTtaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SPTtask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SPTtask.json'

    def parse(self, data: bytes) -> _SPTtaskData:
        reader = BytesReader(data)
        result: _SPTtaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            btlconid: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                btlconid = [reader.ReadSignedInt() for _ in range(num)]

            firstreward: list[int] = []
            if reader.ReadBoolean():
                num2 = reader.ReadSignedInt()
                firstreward = [reader.ReadSignedInt() for _ in range(num2)]

            galaxyid = reader.ReadSignedInt()
            id = reader.ReadSignedInt()
            isend = reader.ReadSignedInt()

            monsterid: list[int] = []
            if reader.ReadBoolean():
                num3 = reader.ReadSignedInt()
                monsterid = [reader.ReadSignedInt() for _ in range(num3)]

            otherreward = reader.ReadUTFBytesWithLength()
            taskmode = reader.ReadSignedInt()
            taskstep = reader.ReadSignedInt()
            tasktype = reader.ReadSignedInt()

            unlockcond: list[int] = []
            if reader.ReadBoolean():
                num4 = reader.ReadSignedInt()
                unlockcond = [reader.ReadSignedInt() for _ in range(num4)]

            unlockmark = reader.ReadSignedInt()

            item: SPTtaskItem = {
                'btlconid': btlconid,
                'firstreward': firstreward,
                'galaxyid': galaxyid,
                'id': id,
                'isend': isend,
                'monsterid': monsterid,
                'otherreward': otherreward,
                'taskmode': taskmode,
                'taskstep': taskstep,
                'tasktype': tasktype,
                'unlockcond': unlockcond,
                'unlockmark': unlockmark,
            }
            result['item'].append(item)

        return result
