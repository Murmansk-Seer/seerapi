from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class OriginRecallMainItem(TypedDict):
    beginning: int
    contactid: str
    id: int
    jump: str
    jumptalkgroupId1: int
    jumptalkgroupId2: int
    level: int
    name: str
    petinfo: str
    reward: str
    showdescribe: str
    showtime: str
    showtype: int


class _OriginRecallMainData(TypedDict):
    item: list[OriginRecallMainItem]


class OriginRecallMainParser(BaseParser[_OriginRecallMainData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'OriginRecall_Main.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'OriginRecall_Main.json'

    def parse(self, data: bytes) -> _OriginRecallMainData:
        reader = BytesReader(data)
        result: _OriginRecallMainData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            beginning = reader.ReadSignedInt()
            contactid = reader.ReadUTFBytesWithLength()
            id = reader.ReadSignedInt()
            jump = reader.ReadUTFBytesWithLength()
            jumptalkgroupId1 = reader.ReadSignedInt()
            jumptalkgroupId2 = reader.ReadSignedInt()
            level = reader.ReadSignedInt()
            name = reader.ReadUTFBytesWithLength()
            petinfo = reader.ReadUTFBytesWithLength()
            reward = reader.ReadUTFBytesWithLength()
            showdescribe = reader.ReadUTFBytesWithLength()
            showtime = reader.ReadUTFBytesWithLength()
            showtype = reader.ReadSignedInt()

            item: OriginRecallMainItem = {
                'beginning': beginning,
                'contactid': contactid,
                'id': id,
                'jump': jump,
                'jumptalkgroupId1': jumptalkgroupId1,
                'jumptalkgroupId2': jumptalkgroupId2,
                'level': level,
                'name': name,
                'petinfo': petinfo,
                'reward': reward,
                'showdescribe': showdescribe,
                'showtime': showtime,
                'showtype': showtype,
            }
            result['item'].append(item)

        return result
