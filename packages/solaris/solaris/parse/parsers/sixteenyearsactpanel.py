from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class SixteenyearsactpanelItem(TypedDict):
    activitiesshow: str
    begintime: int
    endtime: int
    id: int
    module: int
    notes: str
    showtime: str
    title: str


class _SixteenyearsactpanelData(TypedDict):
    item: list[SixteenyearsactpanelItem]


class SixteenyearsactpanelParser(BaseParser[_SixteenyearsactpanelData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'sixteenyearsactpanel.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'sixteenyearsactpanel.json'

    def parse(self, data: bytes) -> _SixteenyearsactpanelData:
        reader = BytesReader(data)
        result: _SixteenyearsactpanelData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            activitiesshow = reader.ReadUTFBytesWithLength()
            begintime = reader.ReadSignedInt()
            endtime = reader.ReadSignedInt()
            id = reader.ReadSignedInt()
            module = reader.ReadSignedInt()
            notes = reader.ReadUTFBytesWithLength()
            showtime = reader.ReadUTFBytesWithLength()
            title = reader.ReadUTFBytesWithLength()

            item: SixteenyearsactpanelItem = {
                'activitiesshow': activitiesshow,
                'begintime': begintime,
                'endtime': endtime,
                'id': id,
                'module': module,
                'notes': notes,
                'showtime': showtime,
                'title': title,
            }
            result['item'].append(item)

        return result
