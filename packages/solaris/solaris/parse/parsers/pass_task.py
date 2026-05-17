from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class PassTaskItem(TypedDict):
    describe: str
    name: str
    reward: str
    taskparam: str
    time2: str
    id: int
    init: int
    num: int
    tasktype: int
    time: int
    type: int
    value: int
    weight: int


class _Root(TypedDict):
    item: list[PassTaskItem]


class _PassTaskData(TypedDict):
    root: _Root


class PassTaskParser(BaseParser[_PassTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'pass_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'pass_task.json'

    def parse(self, data: bytes) -> _PassTaskData:
        reader = BytesReader(data)
        result: _PassTaskData = {'root': {'item': []}}

        if not reader.ReadBoolean():
            return result

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: PassTaskItem = {
                'describe': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'init': reader.ReadSignedInt(),
                'name': reader.ReadUTFBytesWithLength(),
                'num': reader.ReadSignedInt(),
                'reward': reader.ReadUTFBytesWithLength(),
                'taskparam': reader.ReadUTFBytesWithLength(),
                'tasktype': reader.ReadSignedInt(),
                'time': reader.ReadSignedInt(),
                'time2': reader.ReadUTFBytesWithLength(),
                'type': reader.ReadSignedInt(),
                'value': reader.ReadSignedInt(),
                'weight': reader.ReadSignedInt(),
            }
            result['root']['item'].append(item)

        return result
