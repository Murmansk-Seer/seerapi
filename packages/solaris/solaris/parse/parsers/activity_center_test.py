from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ActivityCenterTestInfo(TypedDict):
    Go: int
    args: str
    beginning: str
    channel: int
    ending: str
    helptips: int
    iOSreviewshow: int
    id: int
    isShow: int
    labelName: str
    name: str
    redbadge: int
    signType: int
    sorting: int
    statLog: str
    type: int


class _ActivityCenterTestData(TypedDict):
    item: list[ActivityCenterTestInfo]


class ActivityCenterTestParser(BaseParser[_ActivityCenterTestData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'ActivityCenter_test.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'ActivityCenter_test.json'

    def parse(self, data: bytes) -> _ActivityCenterTestData:
        reader = BytesReader(data)
        result: _ActivityCenterTestData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: ActivityCenterTestInfo = {
                'Go': reader.ReadSignedInt(),
                'args': reader.ReadUTFBytesWithLength(),
                'beginning': reader.ReadUTFBytesWithLength(),
                'channel': reader.ReadSignedInt(),
                'ending': reader.ReadUTFBytesWithLength(),
                'helptips': reader.ReadSignedInt(),
                'iOSreviewshow': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'isShow': reader.ReadSignedInt(),
                'labelName': reader.ReadUTFBytesWithLength(),
                'name': reader.ReadUTFBytesWithLength(),
                'redbadge': reader.ReadSignedInt(),
                'signType': reader.ReadSignedInt(),
                'sorting': reader.ReadSignedInt(),
                'statLog': reader.ReadUTFBytesWithLength(),
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
