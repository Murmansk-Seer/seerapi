from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ActivityTaskConfigInfo(TypedDict):
    activityid: int
    describe: str
    id: int
    rewardinfo: str
    tasksubtype: int
    time: int
    timeend: str
    timelimit: str
    timestart: str
    title: str
    userbitbuf: int
    userbitbuf2: str
    userinfo: int
    value: int


class _ActivityTaskConfigData(TypedDict):
    item: list[ActivityTaskConfigInfo]


class ActivityTaskConfigParser(BaseParser[_ActivityTaskConfigData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'Activity_TaskConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'Activity_TaskConfig.json'

    def parse(self, data: bytes) -> _ActivityTaskConfigData:
        reader = BytesReader(data)
        result: _ActivityTaskConfigData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: ActivityTaskConfigInfo = {
                'activityid': reader.ReadSignedInt(),
                'describe': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'rewardinfo': reader.ReadUTFBytesWithLength(),
                'tasksubtype': reader.ReadSignedInt(),
                'time': reader.ReadSignedInt(),
                'timeend': reader.ReadUTFBytesWithLength(),
                'timelimit': reader.ReadUTFBytesWithLength(),
                'timestart': reader.ReadUTFBytesWithLength(),
                'title': reader.ReadUTFBytesWithLength(),
                'userbitbuf': reader.ReadSignedInt(),
                'userbitbuf2': reader.ReadUTFBytesWithLength(),
                'userinfo': reader.ReadSignedInt(),
                'value': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
