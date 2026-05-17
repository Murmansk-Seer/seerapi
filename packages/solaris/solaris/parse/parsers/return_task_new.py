from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ReturnTaskNewItem(TypedDict):
    id: int
    progress: int
    reward: list[int]


class _ReturnTaskNewData(TypedDict):
    item: list[ReturnTaskNewItem]


class ReturnTaskNewParser(BaseParser[_ReturnTaskNewData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'return_task_new.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'return_task_new.json'

    def parse(self, data: bytes) -> _ReturnTaskNewData:
        reader = BytesReader(data)
        result: _ReturnTaskNewData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            id = reader.ReadSignedInt()
            progress = reader.ReadSignedInt()

            reward: list[int] = []
            if reader.ReadBoolean():
                num = reader.ReadSignedInt()
                reward = [reader.ReadSignedInt() for _ in range(num)]

            item: ReturnTaskNewItem = {
                'id': id,
                'progress': progress,
                'reward': reward,
            }
            result['item'].append(item)

        return result
