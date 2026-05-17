from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class NewBraveChallengeItem(TypedDict):
    title: str
    rewardinfo: list[int]
    id: int
    jump: int


class _NewBraveChallengeData(TypedDict):
    item: list[NewBraveChallengeItem]


class NewBraveChallengeParser(BaseParser[_NewBraveChallengeData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'newBraveChallenge.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'newBraveChallenge.json'

    def parse(self, data: bytes) -> _NewBraveChallengeData:
        reader = BytesReader(data)
        result: _NewBraveChallengeData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item_id = reader.ReadSignedInt()
            jump = reader.ReadSignedInt()
            rewardinfo: list[int] = []
            if reader.ReadBoolean():
                rc = reader.ReadSignedInt()
                rewardinfo = [reader.ReadSignedInt() for _ in range(rc)]
            title = reader.ReadUTFBytesWithLength()

            item: NewBraveChallengeItem = {
                'title': title,
                'rewardinfo': rewardinfo,
                'id': item_id,
                'jump': jump,
            }
            result['item'].append(item)

        return result
