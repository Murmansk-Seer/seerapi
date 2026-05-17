from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class OmniCoetusTaskItem(TypedDict):
    describe: str
    rewardinfo: str
    exp: int
    go: int
    id: int
    shareExp: int
    sorting: int
    time: int
    userinfo: int
    value: int


class _OmniCoetusTaskData(TypedDict):
    item: list[OmniCoetusTaskItem]


class OmniCoetusTaskParser(BaseParser[_OmniCoetusTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'omniCoetus_task.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'omniCoetus_task.json'

    def parse(self, data: bytes) -> _OmniCoetusTaskData:
        reader = BytesReader(data)
        result: _OmniCoetusTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: OmniCoetusTaskItem = {
                'describe': reader.ReadUTFBytesWithLength(),
                'exp': reader.ReadSignedInt(),
                'go': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'rewardinfo': reader.ReadUTFBytesWithLength(),
                'shareExp': reader.ReadSignedInt(),
                'sorting': reader.ReadSignedInt(),
                'time': reader.ReadSignedInt(),
                'userinfo': reader.ReadSignedInt(),
                'value': reader.ReadSignedInt(),
            }
            result['item'].append(item)

        return result
