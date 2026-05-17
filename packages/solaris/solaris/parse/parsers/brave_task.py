from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BraveTaskItem(TypedDict):
    title: str
    jump: list[int]
    rewardinfo: list[int]
    taskparam: list[int]
    group: int
    id: int
    tasktype: int


class _BraveTaskData(TypedDict):
    item: list[BraveTaskItem]


class BraveTaskParser(BaseParser[_BraveTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'brave_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'brave_task.json'

    def parse(self, data: bytes) -> _BraveTaskData:
        reader = BytesReader(data)
        result: _BraveTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            group = reader.ReadSignedInt()
            item_id = reader.ReadSignedInt()
            jump: list[int] = []
            if reader.ReadBoolean():
                jc = reader.ReadSignedInt()
                jump = [reader.ReadSignedInt() for _ in range(jc)]
            rewardinfo: list[int] = []
            if reader.ReadBoolean():
                rc = reader.ReadSignedInt()
                rewardinfo = [reader.ReadSignedInt() for _ in range(rc)]
            taskparam: list[int] = []
            if reader.ReadBoolean():
                tc = reader.ReadSignedInt()
                taskparam = [reader.ReadSignedInt() for _ in range(tc)]
            tasktype = reader.ReadSignedInt()
            title = reader.ReadUTFBytesWithLength()

            item: BraveTaskItem = {
                'title': title,
                'jump': jump,
                'rewardinfo': rewardinfo,
                'taskparam': taskparam,
                'group': group,
                'id': item_id,
                'tasktype': tasktype,
            }
            result['item'].append(item)

        return result
