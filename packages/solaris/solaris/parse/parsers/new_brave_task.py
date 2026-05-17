from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class NewBraveTaskItem(TypedDict):
    title: str
    jump: list[int]
    petreward: list[int]
    rewardinfo: list[int]
    id: int
    pethead: int


class _NewBraveTaskData(TypedDict):
    item: list[NewBraveTaskItem]


class NewBraveTaskParser(BaseParser[_NewBraveTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'newBraveTask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'newBraveTask.json'

    def parse(self, data: bytes) -> _NewBraveTaskData:
        reader = BytesReader(data)
        result: _NewBraveTaskData = {'item': []}

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            item_id = reader.ReadSignedInt()
            jump: list[int] = []
            if reader.ReadBoolean():
                jc = reader.ReadSignedInt()
                jump = [reader.ReadSignedInt() for _ in range(jc)]
            pethead = reader.ReadSignedInt()
            petreward: list[int] = []
            if reader.ReadBoolean():
                pc = reader.ReadSignedInt()
                petreward = [reader.ReadSignedInt() for _ in range(pc)]
            rewardinfo: list[int] = []
            if reader.ReadBoolean():
                rc = reader.ReadSignedInt()
                rewardinfo = [reader.ReadSignedInt() for _ in range(rc)]
            title = reader.ReadUTFBytesWithLength()

            item: NewBraveTaskItem = {
                'title': title,
                'jump': jump,
                'petreward': petreward,
                'rewardinfo': rewardinfo,
                'id': item_id,
                'pethead': pethead,
            }
            result['item'].append(item)

        return result
