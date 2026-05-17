from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class DiamonTaskItem(TypedDict):
    H5go: str
    Rewardcnt: str
    Rewardid: str
    Rewardtype: str
    Taskdescription: str
    Tasktags: str
    id: int
    Taskschedule: int
    Tasktype: int


class _DiamonTaskData(TypedDict):
    item: list[DiamonTaskItem]


class DiamonTaskParser(BaseParser[_DiamonTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'diamon_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'diamon_task.json'

    def parse(self, data: bytes) -> _DiamonTaskData:
        reader = BytesReader(data)
        result: _DiamonTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: DiamonTaskItem = {
                'H5go': reader.ReadUTFBytesWithLength(),
                'Rewardcnt': reader.ReadUTFBytesWithLength(),
                'Rewardid': reader.ReadUTFBytesWithLength(),
                'Rewardtype': reader.ReadUTFBytesWithLength(),
                'Taskdescription': reader.ReadUTFBytesWithLength(),
                'Taskschedule': reader.ReadSignedInt(),
                'Tasktags': reader.ReadUTFBytesWithLength(),
                'Tasktype': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
            }
            result['item'].append(item)

        return result
