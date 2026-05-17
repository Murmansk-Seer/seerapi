from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class YearPetTrain2025Item(TypedDict):
    battlecond: str
    bossid: str
    id: int
    prizedes: str
    prizedetail: str
    storyid: int
    time: int


class _YearPetTrain2025Data(TypedDict):
    item: list[YearPetTrain2025Item]


class YearPetTrain2025Parser(BaseParser[_YearPetTrain2025Data]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'YearPetTrain2025.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'YearPetTrain2025.json'

    def parse(self, data: bytes) -> _YearPetTrain2025Data:
        reader = BytesReader(data)
        result: _YearPetTrain2025Data = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            battlecond = reader.ReadUTFBytesWithLength()
            bossid = reader.ReadUTFBytesWithLength()
            id = reader.ReadSignedInt()
            prizedes = reader.ReadUTFBytesWithLength()
            prizedetail = reader.ReadUTFBytesWithLength()
            storyid = reader.ReadSignedInt()
            time = reader.ReadSignedInt()

            item: YearPetTrain2025Item = {
                'battlecond': battlecond,
                'bossid': bossid,
                'id': id,
                'prizedes': prizedes,
                'prizedetail': prizedetail,
                'storyid': storyid,
                'time': time,
            }
            result['item'].append(item)

        return result
