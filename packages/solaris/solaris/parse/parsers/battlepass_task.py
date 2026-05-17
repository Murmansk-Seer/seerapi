from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BattlepassTaskItem(TypedDict):
    describe: str
    timeend: str
    timelimit: str
    timestart: str
    exp: int
    id: int
    time: int
    userinfo: int
    value: int


class _BattlepassTaskData(TypedDict):
    item: list[BattlepassTaskItem]


class BattlepassTaskParser(BaseParser[_BattlepassTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'battlepass_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'battlepass_task.json'

    def parse(self, data: bytes) -> _BattlepassTaskData:
        reader = BytesReader(data)
        result: _BattlepassTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: BattlepassTaskItem = {
                'describe': reader.ReadUTFBytesWithLength(),
                'exp': reader.ReadSignedInt(),
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
