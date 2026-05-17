from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AdAstraLevelInfo(TypedDict):
    banPet: str
    bossID: str
    condition: str
    firstAward: str
    id: int
    levelName: str
    type: int


class _AdAstraLevelData(TypedDict):
    item: list[AdAstraLevelInfo]


class AdAstraLevelParser(BaseParser[_AdAstraLevelData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AdAstraLevel.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AdAstraLevel.json'

    def parse(self, data: bytes) -> _AdAstraLevelData:
        reader = BytesReader(data)
        result: _AdAstraLevelData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AdAstraLevelInfo = {
                'banPet': reader.ReadUTFBytesWithLength(),
                'bossID': reader.ReadUTFBytesWithLength(),
                'condition': reader.ReadUTFBytesWithLength(),
                'firstAward': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'levelName': reader.ReadUTFBytesWithLength(),
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
