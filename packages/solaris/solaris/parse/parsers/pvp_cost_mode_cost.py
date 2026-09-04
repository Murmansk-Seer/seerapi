from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class PvpCostModeCostInfo(TypedDict):
    cost: int
    id: int
    name: str
    pet: str
    subkeyMonth: int
    subkeyTotal: int
    time: str


class PvpCostModeCostConfig(TypedDict):
    item: list[PvpCostModeCostInfo]


class PvpCostModeCostParser(BaseParser[PvpCostModeCostConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'pvpCostMode_cost.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'pvpCostMode_cost.json'

    def parse(self, data: bytes) -> PvpCostModeCostConfig:
        reader = BytesReader(data)
        result: PvpCostModeCostConfig = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: PvpCostModeCostInfo = {
                'cost': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'name': reader.ReadUTFBytesWithLength(),
                'pet': reader.ReadUTFBytesWithLength(),
                'subkeyMonth': reader.ReadSignedInt(),
                'subkeyTotal': reader.ReadSignedInt(),
                'time': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)

        return result
