from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AdAstraStarAwardInfo(TypedDict):
    id: int
    progress: int
    progressAward: str
    star: int


class _AdAstraStarAwardData(TypedDict):
    item: list[AdAstraStarAwardInfo]


class AdAstraStarAwardParser(BaseParser[_AdAstraStarAwardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AdAstraStarAward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AdAstraStarAward.json'

    def parse(self, data: bytes) -> _AdAstraStarAwardData:
        reader = BytesReader(data)
        result: _AdAstraStarAwardData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AdAstraStarAwardInfo = {
                'id': reader.ReadSignedInt(),
                'progress': reader.ReadSignedInt(),
                'progressAward': reader.ReadUTFBytesWithLength(),
                'star': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
