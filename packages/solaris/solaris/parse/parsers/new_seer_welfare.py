from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class NewSeerWelfareItem(TypedDict):
    Go: int
    beginning: str
    ending: str
    id: int
    name: str
    redPointID: int
    sorting: int
    statLog: str
    type: int


class _NewSeerWelfareData(TypedDict):
    item: list[NewSeerWelfareItem]


class NewSeerWelfareParser(BaseParser[_NewSeerWelfareData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'NewSeerWelfare.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'NewSeerWelfare.json'

    def parse(self, data: bytes) -> _NewSeerWelfareData:
        reader = BytesReader(data)
        result: _NewSeerWelfareData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            Go = reader.ReadSignedInt()
            beginning = reader.ReadUTFBytesWithLength()
            ending = reader.ReadUTFBytesWithLength()
            id = reader.ReadSignedInt()
            name = reader.ReadUTFBytesWithLength()
            redPointID = reader.ReadSignedInt()
            sorting = reader.ReadSignedInt()
            statLog = reader.ReadUTFBytesWithLength()
            type = reader.ReadSignedInt()

            item: NewSeerWelfareItem = {
                'Go': Go,
                'beginning': beginning,
                'ending': ending,
                'id': id,
                'name': name,
                'redPointID': redPointID,
                'sorting': sorting,
                'statLog': statLog,
                'type': type,
            }
            result['item'].append(item)

        return result
