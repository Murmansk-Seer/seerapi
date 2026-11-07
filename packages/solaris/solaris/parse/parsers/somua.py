"""Static layouts verified against GameLogic 20261105235600 Parse methods."""

from typing import TypedDict, cast

from ..base import BaseParser
from ..bytes_reader import BytesReader


def _parse(data: bytes, fields: tuple[tuple[str, str], ...]) -> dict:
    reader = BytesReader(data)
    rows = []
    seen = set()
    if reader.ReadBoolean():
        count = reader.ReadSignedInt()
        if count < 0 or count > reader.remaining() // 4:
            raise ValueError('Invalid Somua record count')
        for _ in range(count):
            row = {}
            for name, kind in fields:
                if kind == 'string':
                    value = reader.ReadUTFBytesWithLength()
                elif kind == 'int32[]':
                    value = None
                    if reader.ReadBoolean():
                        size = reader.ReadSignedInt()
                        if size < 0 or size > reader.remaining() // 4:
                            raise ValueError('Invalid Somua array length')
                        value = [reader.ReadSignedInt() for _ in range(size)]
                else:
                    value = reader.ReadSignedInt()
                row[name] = value
            if row['id'] in seen:
                raise ValueError('Duplicate Somua primary key')
            seen.add(row['id'])
            rows.append(row)
    if not reader.eof():
        raise ValueError('Unconsumed Somua bytes')
    return {'data': rows}


class SomuaAchievementInfo(TypedDict):
    condition: int
    desc: str
    icon: int
    id: int
    name: str
    type: int


class SomuaAchievementConfig(TypedDict):
    data: list[SomuaAchievementInfo]


class SomuaAchievementParser(BaseParser[SomuaAchievementConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaAchievementConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaAchievementConfig.json'

    def parse(self, data: bytes) -> SomuaAchievementConfig:
        return cast(
            SomuaAchievementConfig,
            _parse(
                data,
                (
                    ('condition', 'int32'),
                    ('desc', 'string'),
                    ('icon', 'int32'),
                    ('id', 'int32'),
                    ('name', 'string'),
                    ('type', 'int32'),
                ),
            ),
        )


class SomuaBasicAttributeInfo(TypedDict):
    attack_ratio: int
    attack_value: int
    critical_chance: int
    critical_damage_ratio: int
    defense_ratio: int
    health_value: int
    id: int
    knock_ratio: int
    speed_value: int


class SomuaBasicAttributeConfig(TypedDict):
    data: list[SomuaBasicAttributeInfo]


class SomuaBasicAttributeParser(BaseParser[SomuaBasicAttributeConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaBasicAttritube.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaBasicAttritube.json'

    def parse(self, data: bytes) -> SomuaBasicAttributeConfig:
        return cast(
            SomuaBasicAttributeConfig,
            _parse(
                data,
                (
                    ('attack_ratio', 'int32'),
                    ('attack_value', 'int32'),
                    ('critical_chance', 'int32'),
                    ('critical_damage_ratio', 'int32'),
                    ('defense_ratio', 'int32'),
                    ('health_value', 'int32'),
                    ('id', 'int32'),
                    ('knock_ratio', 'int32'),
                    ('speed_value', 'int32'),
                ),
            ),
        )


class SomuaDispatchInfo(TypedDict):
    award: str
    bonus1: str
    bonus2: str
    bonus3: str
    id: int
    name: str
    tasktype: int
    value: int


class SomuaDispatchConfig(TypedDict):
    data: list[SomuaDispatchInfo]


class SomuaDispatchParser(BaseParser[SomuaDispatchConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaDispatchConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaDispatchConfig.json'

    def parse(self, data: bytes) -> SomuaDispatchConfig:
        return cast(
            SomuaDispatchConfig,
            _parse(
                data,
                (
                    ('award', 'string'),
                    ('bonus1', 'string'),
                    ('bonus2', 'string'),
                    ('bonus3', 'string'),
                    ('id', 'int32'),
                    ('name', 'string'),
                    ('tasktype', 'int32'),
                    ('value', 'int32'),
                ),
            ),
        )


class SomuaEntryInfo(TypedDict):
    desc: str
    id: int
    name: str
    rarity: int
    type: int
    value1: int
    value2: int
    value3: int
    value4: int
    value5: int
    value6: int


class SomuaEntryConfig(TypedDict):
    data: list[SomuaEntryInfo]


class SomuaEntryParser(BaseParser[SomuaEntryConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaEntryConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaEntryConfig.json'

    def parse(self, data: bytes) -> SomuaEntryConfig:
        return cast(
            SomuaEntryConfig,
            _parse(
                data,
                (
                    ('desc', 'string'),
                    ('id', 'int32'),
                    ('name', 'string'),
                    ('rarity', 'int32'),
                    ('type', 'int32'),
                    ('value1', 'int32'),
                    ('value2', 'int32'),
                    ('value3', 'int32'),
                    ('value4', 'int32'),
                    ('value5', 'int32'),
                    ('value6', 'int32'),
                ),
            ),
        )


class SomuaGeneInfo(TypedDict):
    foodid: int
    gene: str
    id: int
    rarity: int
    shop_id: int
    skinbaby: str
    skinteen: str
    sort: int


class SomuaGeneConfig(TypedDict):
    data: list[SomuaGeneInfo]


class SomuaGeneParser(BaseParser[SomuaGeneConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaGeneConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaGeneConfig.json'

    def parse(self, data: bytes) -> SomuaGeneConfig:
        return cast(
            SomuaGeneConfig,
            _parse(
                data,
                (
                    ('foodid', 'int32'),
                    ('gene', 'string'),
                    ('id', 'int32'),
                    ('rarity', 'int32'),
                    ('shop_id', 'int32'),
                    ('skinbaby', 'string'),
                    ('skinteen', 'string'),
                    ('sort', 'int32'),
                ),
            ),
        )


class SomuaHouseInfo(TypedDict):
    id: int
    limit_cost: int
    name: str
    room_id: int


class SomuaHouseConfig(TypedDict):
    data: list[SomuaHouseInfo]


class SomuaHouseParser(BaseParser[SomuaHouseConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaHouseConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaHouseConfig.json'

    def parse(self, data: bytes) -> SomuaHouseConfig:
        return cast(
            SomuaHouseConfig,
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


class SomuaKeeperInfo(TypedDict):
    benefit1: int
    benefit2: int
    benefit3: int
    benefit4: int
    benefit5: int
    benefit6: int
    benefit7: int
    dango_gold: int
    dango_task: str
    describe1: str
    describe2: str
    describe3: str
    id: int
    minor_num: int
    reward: str
    store_max: int
    task_num: int


class SomuaKeeperConfig(TypedDict):
    data: list[SomuaKeeperInfo]


class SomuaKeeperParser(BaseParser[SomuaKeeperConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaKeeperConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaKeeperConfig.json'

    def parse(self, data: bytes) -> SomuaKeeperConfig:
        return cast(
            SomuaKeeperConfig,
            _parse(
                data,
                (
                    ('benefit1', 'int32'),
                    ('benefit2', 'int32'),
                    ('benefit3', 'int32'),
                    ('benefit4', 'int32'),
                    ('benefit5', 'int32'),
                    ('benefit6', 'int32'),
                    ('benefit7', 'int32'),
                    ('dango_gold', 'int32'),
                    ('dango_task', 'string'),
                    ('describe1', 'string'),
                    ('describe2', 'string'),
                    ('describe3', 'string'),
                    ('id', 'int32'),
                    ('minor_num', 'int32'),
                    ('reward', 'string'),
                    ('store_max', 'int32'),
                    ('task_num', 'int32'),
                ),
            ),
        )


class SomuaModelInfo(TypedDict):
    attack_mode: int
    attack_mode_sp: int
    describe: str
    id: int
    is_back: int
    is_body: int
    is_ear: int
    is_expression: int
    is_hand: int
    is_head: int
    is_surrounding: int
    is_tail: int
    is_topwear: int
    name: str
    pet_id: int
    prefix: str
    season: str
    suffix: str


class SomuaModelConfig(TypedDict):
    data: list[SomuaModelInfo]


class SomuaModelParser(BaseParser[SomuaModelConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaModelConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaModelConfig.json'

    def parse(self, data: bytes) -> SomuaModelConfig:
        return cast(
            SomuaModelConfig,
            _parse(
                data,
                (
                    ('attack_mode', 'int32'),
                    ('attack_mode_sp', 'int32'),
                    ('describe', 'string'),
                    ('id', 'int32'),
                    ('is_back', 'int32'),
                    ('is_body', 'int32'),
                    ('is_ear', 'int32'),
                    ('is_expression', 'int32'),
                    ('is_hand', 'int32'),
                    ('is_head', 'int32'),
                    ('is_surrounding', 'int32'),
                    ('is_tail', 'int32'),
                    ('is_topwear', 'int32'),
                    ('name', 'string'),
                    ('pet_id', 'int32'),
                    ('prefix', 'string'),
                    ('season', 'string'),
                    ('suffix', 'string'),
                ),
            ),
        )


class SomuaRankingInfo(TypedDict):
    icon: int
    id: int
    is_falling: int
    level: str
    minscore: str
    name: str
    phase: int


class SomuaRankingConfig(TypedDict):
    data: list[SomuaRankingInfo]


class SomuaRankingParser(BaseParser[SomuaRankingConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaRankingConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaRankingConfig.json'

    def parse(self, data: bytes) -> SomuaRankingConfig:
        return cast(
            SomuaRankingConfig,
            _parse(
                data,
                (
                    ('icon', 'int32'),
                    ('id', 'int32'),
                    ('is_falling', 'int32'),
                    ('level', 'string'),
                    ('minscore', 'string'),
                    ('name', 'string'),
                    ('phase', 'int32'),
                ),
            ),
        )


class SomuaShopInfo(TypedDict):
    new_msglog_id: int
    price: int
    describe1: str
    describe2: str
    forever: int
    id: int
    limit: int
    limit_type: int
    quantity: int
    rewardinfo: str
    shop_type1: int
    title: str
    userinfo: int
    value: int


class SomuaShopConfig(TypedDict):
    data: list[SomuaShopInfo]


class SomuaShopParser(BaseParser[SomuaShopConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaShopConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaShopConfig.json'

    def parse(self, data: bytes) -> SomuaShopConfig:
        return cast(
            SomuaShopConfig,
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
                    ('limit_type', 'int32'),
                    ('quantity', 'int32'),
                    ('rewardinfo', 'string'),
                    ('shop_type1', 'int32'),
                    ('title', 'string'),
                    ('userinfo', 'int32'),
                    ('value', 'int32'),
                ),
            ),
        )


class SomuaStatusEffectInfo(TypedDict):
    fx_on_get: str
    fx_on_trig: str
    icon: int
    id: int
    max_stack: int
    stack_rule: str
    status_desc: str
    status_name: str
    type: int
    value_rule: str


class SomuaStatusEffectConfig(TypedDict):
    data: list[SomuaStatusEffectInfo]


class SomuaStatusEffectParser(BaseParser[SomuaStatusEffectConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaStatusEffectConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaStatusEffectConfig.json'

    def parse(self, data: bytes) -> SomuaStatusEffectConfig:
        return cast(
            SomuaStatusEffectConfig,
            _parse(
                data,
                (
                    ('fx_on_get', 'string'),
                    ('fx_on_trig', 'string'),
                    ('icon', 'int32'),
                    ('id', 'int32'),
                    ('max_stack', 'int32'),
                    ('stack_rule', 'string'),
                    ('status_desc', 'string'),
                    ('status_name', 'string'),
                    ('type', 'int32'),
                    ('value_rule', 'string'),
                ),
            ),
        )


class SomuaTaskInfo(TypedDict):
    describe: str
    group: int
    id: int
    period: int
    rewardinfo: str
    season: int
    tasktype: int
    value: int


class SomuaTaskConfig(TypedDict):
    data: list[SomuaTaskInfo]


class SomuaTaskParser(BaseParser[SomuaTaskConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaTaskConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaTaskConfig.json'

    def parse(self, data: bytes) -> SomuaTaskConfig:
        return cast(
            SomuaTaskConfig,
            _parse(
                data,
                (
                    ('describe', 'string'),
                    ('group', 'int32'),
                    ('id', 'int32'),
                    ('period', 'int32'),
                    ('rewardinfo', 'string'),
                    ('season', 'int32'),
                    ('tasktype', 'int32'),
                    ('value', 'int32'),
                ),
            ),
        )


class SomuaTutorialInfo(TypedDict):
    id: int
    img: str
    module: str
    page: int
    txt: str


class SomuaTutorialConfig(TypedDict):
    data: list[SomuaTutorialInfo]


class SomuaTutorialParser(BaseParser[SomuaTutorialConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaToturialConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaToturialConfig.json'

    def parse(self, data: bytes) -> SomuaTutorialConfig:
        return cast(
            SomuaTutorialConfig,
            _parse(
                data,
                (
                    ('id', 'int32'),
                    ('img', 'string'),
                    ('module', 'string'),
                    ('page', 'int32'),
                    ('txt', 'string'),
                ),
            ),
        )


class SomuaWeaponInfo(TypedDict):
    fx_on_hit: str
    id: int
    prefab: str
    shape: int
    type: int


class SomuaWeaponConfig(TypedDict):
    data: list[SomuaWeaponInfo]


class SomuaWeaponParser(BaseParser[SomuaWeaponConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaWeaponConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaWeaponConfig.json'

    def parse(self, data: bytes) -> SomuaWeaponConfig:
        return cast(
            SomuaWeaponConfig,
            _parse(
                data,
                (
                    ('fx_on_hit', 'string'),
                    ('id', 'int32'),
                    ('prefab', 'string'),
                    ('shape', 'int32'),
                    ('type', 'int32'),
                ),
            ),
        )
