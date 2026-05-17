from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class NatolesJourneyOfRevivalEventConfigInfo(TypedDict):
    des: str
    firstShow: str
    id: int
    name: str
    secondShow: str
    type: int


class _NatolesJourneyOfRevivalEventConfigData(TypedDict):
    item: list[NatolesJourneyOfRevivalEventConfigInfo]


class NatolesJourneyOfRevivalEventConfigParser(
    BaseParser[_NatolesJourneyOfRevivalEventConfigData]
):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'natolesJourneyOfRevivalEventConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'natolesJourneyOfRevivalEventConfig.json'

    def parse(self, data: bytes) -> _NatolesJourneyOfRevivalEventConfigData:
        reader = BytesReader(data)
        result: _NatolesJourneyOfRevivalEventConfigData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: NatolesJourneyOfRevivalEventConfigInfo = {
                'des': reader.ReadUTFBytesWithLength(),
                'firstShow': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'name': reader.ReadUTFBytesWithLength(),
                'secondShow': reader.ReadUTFBytesWithLength(),
                'type': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
