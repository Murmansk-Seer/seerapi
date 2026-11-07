"""Legacy dango layouts, independently decoded from the same client."""

from typing import TypedDict, cast

from ..base import BaseParser
from .somua import _parse


class DangoInfo(TypedDict):
    describe: str
    gene: str
    grade: int
    id: int
    name: str
    pet_id: int
    skin: str
    value: int


class DangoConfig(TypedDict):
    data: list[DangoInfo]


class DangoParser(BaseParser[DangoConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dango.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dango.json'

    def parse(self, data: bytes) -> DangoConfig:
        return cast(
            DangoConfig,
            _parse(
                data,
                (
                    ('describe', 'string'),
                    ('gene', 'string'),
                    ('grade', 'int32'),
                    ('id', 'int32'),
                    ('name', 'string'),
                    ('pet_id', 'int32'),
                    ('skin', 'string'),
                    ('value', 'int32'),
                ),
            ),
        )


class DangoActionInfo(TypedDict):
    action: str
    action_team: int
    dango_id: list[int] | None
    describ: str
    id: int
    limit_dango: int
    limit_type: int
    value: int


class DangoActionConfig(TypedDict):
    data: list[DangoActionInfo]


class DangoActionParser(BaseParser[DangoActionConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoAction.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoAction.json'

    def parse(self, data: bytes) -> DangoActionConfig:
        return cast(
            DangoActionConfig,
            _parse(
                data,
                (
                    ('action', 'string'),
                    ('action_team', 'int32'),
                    ('dango_id', 'int32[]'),
                    ('describ', 'string'),
                    ('id', 'int32'),
                    ('limit_dango', 'int32'),
                    ('limit_type', 'int32'),
                    ('value', 'int32'),
                ),
            ),
        )


class DangoGeneInfo(TypedDict):
    gene_id: int
    id: int
    name: str
    skinbaby: str
    skinteen: str
    value: int


class DangoGeneConfig(TypedDict):
    data: list[DangoGeneInfo]


class DangoGeneParser(BaseParser[DangoGeneConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoGene.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoGene.json'

    def parse(self, data: bytes) -> DangoGeneConfig:
        return cast(
            DangoGeneConfig,
            _parse(
                data,
                (
                    ('gene_id', 'int32'),
                    ('id', 'int32'),
                    ('name', 'string'),
                    ('skinbaby', 'string'),
                    ('skinteen', 'string'),
                    ('value', 'int32'),
                ),
            ),
        )


class DangoGoldInfo(TypedDict):
    dango_gold: int
    dango_num_max: int
    dango_num_mix: int
    id: int


class DangoGoldConfig(TypedDict):
    data: list[DangoGoldInfo]


class DangoGoldParser(BaseParser[DangoGoldConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoGold.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoGold.json'

    def parse(self, data: bytes) -> DangoGoldConfig:
        return cast(
            DangoGoldConfig,
            _parse(
                data,
                (
                    ('dango_gold', 'int32'),
                    ('dango_num_max', 'int32'),
                    ('dango_num_mix', 'int32'),
                    ('id', 'int32'),
                ),
            ),
        )


class DangoGuideInfo(TypedDict):
    dango_movie: str
    describe: str
    id: int
    reward: str
    titile: str
    type: int


class DangoGuideConfig(TypedDict):
    data: list[DangoGuideInfo]


class DangoGuideParser(BaseParser[DangoGuideConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoGuide.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoGuide.json'

    def parse(self, data: bytes) -> DangoGuideConfig:
        return cast(
            DangoGuideConfig,
            _parse(
                data,
                (
                    ('dango_movie', 'string'),
                    ('describe', 'string'),
                    ('id', 'int32'),
                    ('reward', 'string'),
                    ('titile', 'string'),
                    ('type', 'int32'),
                ),
            ),
        )


class DangoHouseInfo(TypedDict):
    id: int
    limit_cost: int
    name: str
    room_id: int


class DangoHouseConfig(TypedDict):
    data: list[DangoHouseInfo]


class DangoHouseParser(BaseParser[DangoHouseConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoHouse.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoHouse.json'

    def parse(self, data: bytes) -> DangoHouseConfig:
        return cast(
            DangoHouseConfig,
            _parse(
                data,
                (
                    ('id', 'int32'),
                    ('limit_cost', 'int32'),
                    ('name', 'string'),
                    ('room_id', 'int32'),
                ),
            ),
        )


class DangoLevelInfo(TypedDict):
    benefit1: int
    benefit2: int
    benefit3: int
    dango_task: list[int] | None
    describe1: str
    describe2: str
    describe3: str
    id: int
    minor_num: int
    reward: int
    task_num: int


class DangoLevelConfig(TypedDict):
    data: list[DangoLevelInfo]


class DangoLevelParser(BaseParser[DangoLevelConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoLv.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoLv.json'

    def parse(self, data: bytes) -> DangoLevelConfig:
        return cast(
            DangoLevelConfig,
            _parse(
                data,
                (
                    ('benefit1', 'int32'),
                    ('benefit2', 'int32'),
                    ('benefit3', 'int32'),
                    ('dango_task', 'int32[]'),
                    ('describe1', 'string'),
                    ('describe2', 'string'),
                    ('describe3', 'string'),
                    ('id', 'int32'),
                    ('minor_num', 'int32'),
                    ('reward', 'int32'),
                    ('task_num', 'int32'),
                ),
            ),
        )


class DangoShopInfo(TypedDict):
    new_msglog_id: int
    price: int
    describe1: str
    describe2: str
    forever: int
    id: int
    limit: int
    quantity: int
    rewardinfo: str
    shop_type1: int
    shop_type2: int
    title: str
    userinfo: int
    value: int


class DangoShopConfig(TypedDict):
    data: list[DangoShopInfo]


class DangoShopParser(BaseParser[DangoShopConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoShop.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoShop.json'

    def parse(self, data: bytes) -> DangoShopConfig:
        return cast(
            DangoShopConfig,
            _parse(
                data,
                (
                    ('new_msglog_id', 'int32'),
                    ('price', 'int32'),
                    ('describe1', 'string'),
                    ('describe2', 'string'),
                    ('forever', 'int32'),
                    ('id', 'int32'),
                    ('limit', 'int32'),
                    ('quantity', 'int32'),
                    ('rewardinfo', 'string'),
                    ('shop_type1', 'int32'),
                    ('shop_type2', 'int32'),
                    ('title', 'string'),
                    ('userinfo', 'int32'),
                    ('value', 'int32'),
                ),
            ),
        )


class DangoSlotInfo(TypedDict):
    id: int
    name: str
    pet_id: int
    value: int


class DangoSlotConfig(TypedDict):
    data: list[DangoSlotInfo]


class DangoSlotParser(BaseParser[DangoSlotConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoSlot.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoSlot.json'

    def parse(self, data: bytes) -> DangoSlotConfig:
        return cast(
            DangoSlotConfig,
            _parse(
                data,
                (
                    ('id', 'int32'),
                    ('name', 'string'),
                    ('pet_id', 'int32'),
                    ('value', 'int32'),
                ),
            ),
        )


class DangoStoryInfo(TypedDict):
    dango_id: int
    dango_task: int
    describe: str
    id: int


class DangoStoryConfig(TypedDict):
    data: list[DangoStoryInfo]


class DangoStoryParser(BaseParser[DangoStoryConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoStory.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoStory.json'

    def parse(self, data: bytes) -> DangoStoryConfig:
        return cast(
            DangoStoryConfig,
            _parse(
                data,
                (
                    ('dango_id', 'int32'),
                    ('dango_task', 'int32'),
                    ('describe', 'string'),
                    ('id', 'int32'),
                ),
            ),
        )


class DangoTaskInfo(TypedDict):
    new_msglog_id: int
    describe: str
    id: int
    limit: int
    planet: str
    rewardinfo: int
    task_skin: str
    task_team: int
    tasktype: int
    time: int
    title: str
    value: int


class DangoTaskConfig(TypedDict):
    data: list[DangoTaskInfo]


class DangoTaskParser(BaseParser[DangoTaskConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangoTask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangoTask.json'

    def parse(self, data: bytes) -> DangoTaskConfig:
        return cast(
            DangoTaskConfig,
            _parse(
                data,
                (
                    ('new_msglog_id', 'int32'),
                    ('describe', 'string'),
                    ('id', 'int32'),
                    ('limit', 'int32'),
                    ('planet', 'string'),
                    ('rewardinfo', 'int32'),
                    ('task_skin', 'string'),
                    ('task_team', 'int32'),
                    ('tasktype', 'int32'),
                    ('time', 'int32'),
                    ('title', 'string'),
                    ('value', 'int32'),
                ),
            ),
        )


class DangoChessInfo(TypedDict):
    guide_card: str
    cardid: str
    chapterid: int
    dango_id: int
    firstreward: str
    id: int
    stageid: int
    starttime: str


class DangoChessConfig(TypedDict):
    data: list[DangoChessInfo]


class DangoChessParser(BaseParser[DangoChessConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangochess.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangochess.json'

    def parse(self, data: bytes) -> DangoChessConfig:
        return cast(
            DangoChessConfig,
            _parse(
                data,
                (
                    ('guide_card', 'string'),
                    ('cardid', 'string'),
                    ('chapterid', 'int32'),
                    ('dango_id', 'int32'),
                    ('firstreward', 'string'),
                    ('id', 'int32'),
                    ('stageid', 'int32'),
                    ('starttime', 'string'),
                ),
            ),
        )


class DangoChessStageInfo(TypedDict):
    chapterid: int
    hangid: int
    id: int
    lieid1: int
    lieid2: int
    lieid3: int
    lieid4: int
    lieid5: int
    lieid6: int
    lieid7: int
    lieid8: int
    lieid9: int
    stageid: int


class DangoChessStageConfig(TypedDict):
    data: list[DangoChessStageInfo]


class DangoChessStageParser(BaseParser[DangoChessStageConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'dangochessstage.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'dangochessstage.json'

    def parse(self, data: bytes) -> DangoChessStageConfig:
        return cast(
            DangoChessStageConfig,
            _parse(
                data,
                (
                    ('chapterid', 'int32'),
                    ('hangid', 'int32'),
                    ('id', 'int32'),
                    ('lieid1', 'int32'),
                    ('lieid2', 'int32'),
                    ('lieid3', 'int32'),
                    ('lieid4', 'int32'),
                    ('lieid5', 'int32'),
                    ('lieid6', 'int32'),
                    ('lieid7', 'int32'),
                    ('lieid8', 'int32'),
                    ('lieid9', 'int32'),
                    ('stageid', 'int32'),
                ),
            ),
        )
