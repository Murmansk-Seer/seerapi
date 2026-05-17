from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class FireworkQuestActivityStageInfo(TypedDict):
    chapterId: int
    id: int
    stageAward: str
    stageBlockPool: str
    stageSetting: str
    stageStory: str
    stageTarget: str
    stageTutorial: str


class _FireworkQuestActivityStageData(TypedDict):
    item: list[FireworkQuestActivityStageInfo]


class FireworkQuestActivityStageParser(BaseParser[_FireworkQuestActivityStageData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'fireworkQuestActivityStage.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'fireworkQuestActivityStage.json'

    def parse(self, data: bytes) -> _FireworkQuestActivityStageData:
        reader = BytesReader(data)
        result: _FireworkQuestActivityStageData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: FireworkQuestActivityStageInfo = {
                'chapterId': reader.ReadSignedInt(),
                'id': reader.ReadSignedInt(),
                'stageAward': reader.ReadUTFBytesWithLength(),
                'stageBlockPool': reader.ReadUTFBytesWithLength(),
                'stageSetting': reader.ReadUTFBytesWithLength(),
                'stageStory': reader.ReadUTFBytesWithLength(),
                'stageTarget': reader.ReadUTFBytesWithLength(),
                'stageTutorial': reader.ReadUTFBytesWithLength(),
            }
            result['item'].append(item)
        return result
