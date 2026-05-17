from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AdAstraGalaxyGuoqingInfo(TypedDict):
    endTime: int
    galaxyId: int
    galaxyName: str
    galaxyNameEn: str
    galaxyType: int
    id: int
    starId: int
    starLevel: str
    starName: str
    starProgressAll: int
    unlockStar: str
    unlockTime: int


class _AdAstraGalaxyGuoqingData(TypedDict):
    item: list[AdAstraGalaxyGuoqingInfo]


class AdAstraGalaxyGuoqingParser(BaseParser[_AdAstraGalaxyGuoqingData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AdAstraGalaxy_guoqing.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AdAstraGalaxy_guoqing.json'

    def parse(self, data: bytes) -> _AdAstraGalaxyGuoqingData:
        reader = BytesReader(data)
        result: _AdAstraGalaxyGuoqingData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AdAstraGalaxyGuoqingInfo = {
                'endTime': reader.ReadSignedInt(),
                'galaxyId': reader.ReadSignedInt(),
                'galaxyName': reader.ReadUTFBytesWithLength(),
                'galaxyNameEn': reader.ReadUTFBytesWithLength(),
                'galaxyType': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'starId': reader.ReadSignedInt(),
                'starLevel': reader.ReadUTFBytesWithLength(),
                'starName': reader.ReadUTFBytesWithLength(),
                'starProgressAll': reader.ReadSignedInt(),
                'unlockStar': reader.ReadUTFBytesWithLength(),
                'unlockTime': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
