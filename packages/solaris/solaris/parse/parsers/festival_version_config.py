from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class FestivalVersionConfigItem(TypedDict):
    endTime: str
    id: int
    startTime: str
    suffix: str
    tables: str


class _FestivalVersionConfigData(TypedDict):
    item: list[FestivalVersionConfigItem]


class FestivalVersionConfigParser(BaseParser[_FestivalVersionConfigData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'festival_version_config.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'festival_version_config.json'

    def parse(self, data: bytes) -> _FestivalVersionConfigData:
        reader = BytesReader(data)
        result: _FestivalVersionConfigData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            endTime = reader.ReadUTFBytesWithLength()
            id = reader.ReadSignedInt()
            startTime = reader.ReadUTFBytesWithLength()
            suffix = reader.ReadUTFBytesWithLength()
            tables = reader.ReadUTFBytesWithLength()

            item: FestivalVersionConfigItem = {
                'endTime': endTime,
                'id': id,
                'startTime': startTime,
                'suffix': suffix,
                'tables': tables,
            }
            result['item'].append(item)

        return result
