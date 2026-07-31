"""群星牌赛季圣域效果配置解析器。"""

from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AutocardSeasonEffectInfo(TypedDict):
    """一条基础圣域或第 5/10 回合可选效果。"""

    count_buff_id: str
    buff_id: str
    buff_param: str
    count_type: int
    count_num: int
    sanctuary_id: int
    name: str
    description: str
    id: int
    unlock_round: int
    pic_id: int
    season_id: int
    stage: int


class AutocardSeasonEffectConfig(TypedDict):
    """群星牌赛季圣域效果配置。"""

    data: list[AutocardSeasonEffectInfo]


class AutocardSeasonEffectParser(BaseParser[AutocardSeasonEffectConfig]):
    """解析 ``autocardSeasonEffect.bytes`` 配置文件。"""

    @classmethod
    def source_config_filename(cls) -> str:
        return 'autocardSeasonEffect.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'autocardSeasonEffect.json'

    def parse(self, data: bytes) -> AutocardSeasonEffectConfig:
        reader = BytesReader(data)
        result = AutocardSeasonEffectConfig(data=[])

        if not reader.ReadBoolean():
            return result

        count = reader.ReadSignedInt()
        for _ in range(count):
            count_buff_id = reader.ReadUTFBytesWithLength()
            buff_id = reader.ReadUTFBytesWithLength()
            buff_param = reader.ReadUTFBytesWithLength()
            count_type = reader.ReadSignedInt()
            count_num = reader.ReadSignedInt()
            sanctuary_id = reader.ReadSignedInt()
            name = reader.ReadUTFBytesWithLength()
            description = reader.ReadUTFBytesWithLength()
            id_val = reader.ReadSignedInt()
            unlock_round = reader.ReadSignedInt()
            pic_id = reader.ReadSignedInt()
            season_id = reader.ReadSignedInt()
            stage = reader.ReadSignedInt()

            result['data'].append(
                AutocardSeasonEffectInfo(
                    count_buff_id=count_buff_id,
                    buff_id=buff_id,
                    buff_param=buff_param,
                    count_type=count_type,
                    count_num=count_num,
                    sanctuary_id=sanctuary_id,
                    name=name,
                    description=description,
                    id=id_val,
                    unlock_round=unlock_round,
                    pic_id=pic_id,
                    season_id=season_id,
                    stage=stage,
                )
            )

        return result
