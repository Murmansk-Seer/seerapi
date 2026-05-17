from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ActivityCenterInfo(TypedDict):
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
    type: int


class _ActivityCenterData(TypedDict):
    item: list[ActivityCenterInfo]


class ActivityCenterParser(BaseParser[_ActivityCenterData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'ActivityCenter.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'ActivityCenter.json'

    def parse(self, data: bytes) -> _ActivityCenterData:
        reader = BytesReader(data)
        result: _ActivityCenterData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: ActivityCenterInfo = {
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
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result


class ActivityCenterBisaifuInfo(TypedDict):
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
    type: int


class _ActivityCenterBisaifuData(TypedDict):
    item: list[ActivityCenterBisaifuInfo]


class ActivityCenterBisaifuParser(BaseParser[_ActivityCenterBisaifuData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'ActivityCenter_bisaifu.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'ActivityCenter_bisaifu.json'

    def parse(self, data: bytes) -> _ActivityCenterBisaifuData:
        reader = BytesReader(data)
        result: _ActivityCenterBisaifuData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: ActivityCenterBisaifuInfo = {
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
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
