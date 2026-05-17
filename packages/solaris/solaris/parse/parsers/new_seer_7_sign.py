from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class NewSeer7SignItem(TypedDict):
    Amount: int
    Daycount: str
    GiftID: str
    GiftName: str
    GiftType: str
    Rare: int
    id: int


class _NewSeer7SignData(TypedDict):
    item: list[NewSeer7SignItem]


class NewSeer7SignParser(BaseParser[_NewSeer7SignData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'newSeer7Sign.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'newSeer7Sign.json'

    def parse(self, data: bytes) -> _NewSeer7SignData:
        reader = BytesReader(data)
        result: _NewSeer7SignData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            Amount = reader.ReadSignedInt()
            Daycount = reader.ReadUTFBytesWithLength()
            GiftID = reader.ReadUTFBytesWithLength()
            GiftName = reader.ReadUTFBytesWithLength()
            GiftType = reader.ReadUTFBytesWithLength()
            Rare = reader.ReadSignedInt()
            id = reader.ReadSignedInt()

            item: NewSeer7SignItem = {
                'Amount': Amount,
                'Daycount': Daycount,
                'GiftID': GiftID,
                'GiftName': GiftName,
                'GiftType': GiftType,
                'Rare': Rare,
                'id': id,
            }
            result['item'].append(item)

        return result
