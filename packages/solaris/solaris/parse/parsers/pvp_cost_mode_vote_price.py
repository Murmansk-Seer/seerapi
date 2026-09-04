from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class PvpCostModeVotePriceInfo(TypedDict):
    id: int
    price: int
    rank: int


class PvpCostModeVotePriceConfig(TypedDict):
    item: list[PvpCostModeVotePriceInfo]


class PvpCostModeVotePriceParser(BaseParser[PvpCostModeVotePriceConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'pvpCostMode_votePrice.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'pvpCostMode_votePrice.json'

    def parse(self, data: bytes) -> PvpCostModeVotePriceConfig:
        reader = BytesReader(data)
        result: PvpCostModeVotePriceConfig = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: PvpCostModeVotePriceInfo = {
                'id': reader.ReadSignedInt(),
                'price': reader.ReadSignedInt(),
                'rank': reader.ReadSignedInt(),
            }
            result['item'].append(item)

        return result
