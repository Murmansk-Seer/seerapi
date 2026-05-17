from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class OmniCoetusRewardItem(TypedDict):
    reward: str
    exp: int
    id: int
    stat: int


class _OmniCoetusRewardData(TypedDict):
    item: list[OmniCoetusRewardItem]


class OmniCoetusRewardParser(BaseParser[_OmniCoetusRewardData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'omniCoetus_reward.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'omniCoetus_reward.json'

    def parse(self, data: bytes) -> _OmniCoetusRewardData:
        reader = BytesReader(data)
        result: _OmniCoetusRewardData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item: OmniCoetusRewardItem = {
                'exp': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'reward': reader.ReadUTFBytesWithLength(),
                'stat': reader.ReadSignedInt(),
            }
            result['item'].append(item)

        return result
