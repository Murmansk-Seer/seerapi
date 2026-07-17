from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ActivityTimeUpdateInfo(TypedDict):
    beginning: str
    ending: str
    id: int
    name: str
    parameters1: int
    parameters2: int
    parameters3: int
    parameters4: int
    parametersDesc: str


class _Root(TypedDict):
    item: list[ActivityTimeUpdateInfo]


class ActivityTimeUpdateConfig(TypedDict):
    root: _Root


class ActivityTimeUpdateConfigParser(BaseParser[ActivityTimeUpdateConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'Activity_TimeUpdateConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'activityTimeUpdateConfig.json'

    def parse(self, data: bytes) -> ActivityTimeUpdateConfig:
        reader = BytesReader(data)
        result: ActivityTimeUpdateConfig = {'root': {'item': []}}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: ActivityTimeUpdateInfo = {
                'beginning': reader.ReadUTFBytesWithLength(),
                'ending': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'name': reader.ReadUTFBytesWithLength(),
                'parameters1': reader.ReadSignedInt(),
                'parameters2': reader.ReadSignedInt(),
                'parameters3': reader.ReadSignedInt(),
                'parameters4': reader.ReadSignedInt(),
                'parametersDesc': reader.ReadUTFBytesWithLength(),
            }
            result['root']['item'].append(item)

        return result
