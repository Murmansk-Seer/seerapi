from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class ExplorationRewardInfo(TypedDict):
    class_: int
    currency: int
    currencynum: int
    id: int
    item: int
    limit: int
    number: int
    sort: int
    starting: int
    type: int
    user_info: int


class _ExplorationRewardData(TypedDict):
    item: list[ExplorationRewardInfo]


class ExplorationRewardParser(BaseParser[_ExplorationRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'ExplorationReward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'ExplorationReward.json'

    def parse(self, data: bytes) -> _ExplorationRewardData:
        reader = BytesReader(data)
        result: _ExplorationRewardData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: ExplorationRewardInfo = {
                'class_': reader.ReadSignedInt(),
                'currency': reader.ReadSignedInt(),
                'currencynum': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'item': reader.ReadSignedInt(),
                'limit': reader.ReadSignedInt(),
                'number': reader.ReadSignedInt(),
                'sort': reader.ReadSignedInt(),
                'starting': reader.ReadSignedInt(),
                'type': reader.ReadSignedInt(),
                'user_info': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
