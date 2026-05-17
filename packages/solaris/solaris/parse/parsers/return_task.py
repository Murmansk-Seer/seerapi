from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ReturnTaskItem(TypedDict):
    id: int
    reward: list[int]
    times: int


class _ReturnTaskData(TypedDict):
    item: list[ReturnTaskItem]


class ReturnTaskParser(BaseParser[_ReturnTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'return_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'return_task.json'

    def parse(self, data: bytes) -> _ReturnTaskData:
        reader = BytesReader(data)
        result: _ReturnTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            id = reader.ReadSignedInt()

            reward: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                reward = [reader.ReadSignedInt() for _ in range(num)]

            times = reader.ReadSignedInt()

            item: ReturnTaskItem = {
                'id': id,
                'reward': reward,
                'times': times,
            }
            result['item'].append(item)

        return result
