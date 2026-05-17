from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BadgeBattlePassTaskItem(TypedDict):
    describe: str
    timeend: str
    timelimit: str
    timestart: str
    exp: int
    go: int
    id: int
    time: int
    userinfo: int
    value: int


class _BadgeBattlePassTaskData(TypedDict):
    item: list[BadgeBattlePassTaskItem]


class BadgeBattlePassTaskParser(BaseParser[_BadgeBattlePassTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'badgeBattlePass_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'badgeBattlePass_task.json'

    def parse(self, data: bytes) -> _BadgeBattlePassTaskData:
        reader = BytesReader(data)
        result: _BadgeBattlePassTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: BadgeBattlePassTaskItem = {
                'describe': reader.ReadUTFBytesWithLength(),
                'exp': reader.ReadSignedInt(),
                'go': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'time': reader.ReadSignedInt(),
                'timeend': reader.ReadUTFBytesWithLength(),
                'timelimit': reader.ReadUTFBytesWithLength(),
                'timestart': reader.ReadUTFBytesWithLength(),
                'userinfo': reader.ReadSignedInt(),
                'value': reader.ReadSignedInt(),
            }
            result['item'].append(item)

        return result
