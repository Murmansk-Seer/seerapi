from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AdAstraConditionInfo(TypedDict):
    btldesc: str
    id: int


class _AdAstraConditionData(TypedDict):
    item: list[AdAstraConditionInfo]


class AdAstraConditionParser(BaseParser[_AdAstraConditionData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AdAstraCondition.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AdAstraCondition.json'

    def parse(self, data: bytes) -> _AdAstraConditionData:
        reader = BytesReader(data)
        result: _AdAstraConditionData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AdAstraConditionInfo = {
                'btldesc': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
