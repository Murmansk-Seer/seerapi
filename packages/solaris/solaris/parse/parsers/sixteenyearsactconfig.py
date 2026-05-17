from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class SixteenyearsactconfigItem(TypedDict):
    activitiesshow: str
    begintime: int
    endtime: int
    gift: int
    id: int
    name: str
    showtime: str
    target: int
    title: str
    type: int


class _SixteenyearsactconfigData(TypedDict):
    item: list[SixteenyearsactconfigItem]


class SixteenyearsactconfigParser(BaseParser[_SixteenyearsactconfigData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'sixteenyearsactconfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'sixteenyearsactconfig.json'

    def parse(self, data: bytes) -> _SixteenyearsactconfigData:
        reader = BytesReader(data)
        result: _SixteenyearsactconfigData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            activitiesshow = reader.ReadUTFBytesWithLength()
            begintime = reader.ReadSignedInt()
            endtime = reader.ReadSignedInt()
            gift = reader.ReadSignedInt()
            id = reader.ReadSignedInt()
            name = reader.ReadUTFBytesWithLength()
            showtime = reader.ReadUTFBytesWithLength()
            target = reader.ReadSignedInt()
            title = reader.ReadUTFBytesWithLength()
            type = reader.ReadSignedInt()

            item: SixteenyearsactconfigItem = {
                'activitiesshow': activitiesshow,
                'begintime': begintime,
                'endtime': endtime,
                'gift': gift,
                'id': id,
                'name': name,
                'showtime': showtime,
                'target': target,
                'title': title,
                'type': type,
            }
            result['item'].append(item)

        return result
