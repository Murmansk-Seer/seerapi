"""Independent Somua and legacy dango resources; numeric values are unscaled."""

from typing import ClassVar

from sqlmodel import Field

from seerapi_models.build_model import BaseResModel, ConvertToORM


class BaseSomuaAchievement(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    condition: int = Field(
        description='Client SomuaAchievementConfig.condition; raw int32'
    )
    desc: str = Field(description='Client SomuaAchievementConfig.desc; raw string')
    icon: int = Field(description='Client SomuaAchievementConfig.icon; raw int32')
    name: str = Field(description='Client SomuaAchievementConfig.name; raw string')
    type: int = Field(description='Client SomuaAchievementConfig.type; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_achievement'


class SomuaAchievement(BaseSomuaAchievement, ConvertToORM['SomuaAchievementORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaAchievementORM']:
        return SomuaAchievementORM

    def to_orm(self) -> 'SomuaAchievementORM':
        return SomuaAchievementORM(**self.model_dump())


class SomuaAchievementORM(BaseSomuaAchievement, table=True):
    pass


class BaseSomuaBasicAttribute(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    attack_ratio: int = Field(
        description='Client SomuaBasicAttritube.attackRatio; raw int32'
    )
    attack_value: int = Field(
        description='Client SomuaBasicAttritube.attackValue; raw int32'
    )
    critical_chance: int = Field(
        description='Client SomuaBasicAttritube.criticalChance; raw int32'
    )
    critical_damage_ratio: int = Field(
        description='Client SomuaBasicAttritube.criticalDamageRatio; raw int32'
    )
    defense_ratio: int = Field(
        description='Client SomuaBasicAttritube.defenseRatio; raw int32'
    )
    health_value: int = Field(
        description='Client SomuaBasicAttritube.healthValue; raw int32'
    )
    knock_ratio: int = Field(
        description='Client SomuaBasicAttritube.knockRatio; raw int32'
    )
    speed_value: int = Field(
        description='Client SomuaBasicAttritube.speedValue; raw int32'
    )

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_basic_attribute'


class SomuaBasicAttribute(
    BaseSomuaBasicAttribute, ConvertToORM['SomuaBasicAttributeORM']
):
    @classmethod
    def get_orm_model(cls) -> type['SomuaBasicAttributeORM']:
        return SomuaBasicAttributeORM

    def to_orm(self) -> 'SomuaBasicAttributeORM':
        return SomuaBasicAttributeORM(**self.model_dump())


class SomuaBasicAttributeORM(BaseSomuaBasicAttribute, table=True):
    pass


class BaseSomuaDispatch(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    award: str = Field(description='Client SomuaDispatchConfig.award; raw string')
    bonus1: str = Field(description='Client SomuaDispatchConfig.bonus1; raw string')
    bonus2: str = Field(description='Client SomuaDispatchConfig.bonus2; raw string')
    bonus3: str = Field(description='Client SomuaDispatchConfig.bonus3; raw string')
    name: str = Field(description='Client SomuaDispatchConfig.name; raw string')
    tasktype: int = Field(description='Client SomuaDispatchConfig.tasktype; raw int32')
    value: int = Field(description='Client SomuaDispatchConfig.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_dispatch'


class SomuaDispatch(BaseSomuaDispatch, ConvertToORM['SomuaDispatchORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaDispatchORM']:
        return SomuaDispatchORM

    def to_orm(self) -> 'SomuaDispatchORM':
        return SomuaDispatchORM(**self.model_dump())


class SomuaDispatchORM(BaseSomuaDispatch, table=True):
    pass


class BaseSomuaEntry(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    desc: str = Field(description='Client SomuaEntryConfig.desc; raw string')
    name: str = Field(description='Client SomuaEntryConfig.name; raw string')
    rarity: int = Field(description='Client SomuaEntryConfig.rarity; raw int32')
    type: int = Field(description='Client SomuaEntryConfig.type; raw int32')
    value1: int = Field(description='Client SomuaEntryConfig.value1; raw int32')
    value2: int = Field(description='Client SomuaEntryConfig.value2; raw int32')
    value3: int = Field(description='Client SomuaEntryConfig.value3; raw int32')
    value4: int = Field(description='Client SomuaEntryConfig.value4; raw int32')
    value5: int = Field(description='Client SomuaEntryConfig.value5; raw int32')
    value6: int = Field(description='Client SomuaEntryConfig.value6; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_entry'


class SomuaEntry(BaseSomuaEntry, ConvertToORM['SomuaEntryORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaEntryORM']:
        return SomuaEntryORM

    def to_orm(self) -> 'SomuaEntryORM':
        return SomuaEntryORM(**self.model_dump())


class SomuaEntryORM(BaseSomuaEntry, table=True):
    pass


class BaseSomuaGene(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['gene']
    foodid: int = Field(description='Client SomuaGeneConfig.foodid; raw int32')
    gene: str = Field(description='Client SomuaGeneConfig.gene; raw string')
    rarity: int = Field(description='Client SomuaGeneConfig.rarity; raw int32')
    shop_id: int = Field(description='Client SomuaGeneConfig.shopID; raw int32')
    skinbaby: str = Field(description='Client SomuaGeneConfig.skinbaby; raw string')
    skinteen: str = Field(description='Client SomuaGeneConfig.skinteen; raw string')
    sort: int = Field(description='Client SomuaGeneConfig.sort; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_gene'


class SomuaGene(BaseSomuaGene, ConvertToORM['SomuaGeneORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaGeneORM']:
        return SomuaGeneORM

    def to_orm(self) -> 'SomuaGeneORM':
        return SomuaGeneORM(**self.model_dump())


class SomuaGeneORM(BaseSomuaGene, table=True):
    pass


class BaseSomuaHouse(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    limit_cost: int = Field(description='Client SomuaHouseConfig.limitCost; raw int32')
    name: str = Field(description='Client SomuaHouseConfig.name; raw string')
    room_id: int = Field(description='Client SomuaHouseConfig.roomID; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_house'


class SomuaHouse(BaseSomuaHouse, ConvertToORM['SomuaHouseORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaHouseORM']:
        return SomuaHouseORM

    def to_orm(self) -> 'SomuaHouseORM':
        return SomuaHouseORM(**self.model_dump())


class SomuaHouseORM(BaseSomuaHouse, table=True):
    pass


class BaseSomuaKeeper(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    benefit1: int = Field(description='Client SomuaKeeperConfig.benefit1; raw int32')
    benefit2: int = Field(description='Client SomuaKeeperConfig.benefit2; raw int32')
    benefit3: int = Field(description='Client SomuaKeeperConfig.benefit3; raw int32')
    benefit4: int = Field(description='Client SomuaKeeperConfig.benefit4; raw int32')
    benefit5: int = Field(description='Client SomuaKeeperConfig.benefit5; raw int32')
    benefit6: int = Field(description='Client SomuaKeeperConfig.benefit6; raw int32')
    benefit7: int = Field(description='Client SomuaKeeperConfig.benefit7; raw int32')
    dango_gold: int = Field(description='Client SomuaKeeperConfig.dangoGold; raw int32')
    dango_task: str = Field(
        description='Client SomuaKeeperConfig.dangoTask; raw string'
    )
    describe1: str = Field(description='Client SomuaKeeperConfig.describe1; raw string')
    describe2: str = Field(description='Client SomuaKeeperConfig.describe2; raw string')
    describe3: str = Field(description='Client SomuaKeeperConfig.describe3; raw string')
    minor_num: int = Field(description='Client SomuaKeeperConfig.minorNum; raw int32')
    reward: str = Field(description='Client SomuaKeeperConfig.reward; raw string')
    store_max: int = Field(description='Client SomuaKeeperConfig.storeMax; raw int32')
    task_num: int = Field(description='Client SomuaKeeperConfig.taskNum; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_keeper'


class SomuaKeeper(BaseSomuaKeeper, ConvertToORM['SomuaKeeperORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaKeeperORM']:
        return SomuaKeeperORM

    def to_orm(self) -> 'SomuaKeeperORM':
        return SomuaKeeperORM(**self.model_dump())


class SomuaKeeperORM(BaseSomuaKeeper, table=True):
    pass


class BaseSomuaModel(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    attack_mode: int = Field(
        description='Client SomuaModelConfig.attackMode; raw int32'
    )
    attack_mode_sp: int = Field(
        description='Client SomuaModelConfig.attackModeSP; raw int32'
    )
    describe: str = Field(description='Client SomuaModelConfig.describe; raw string')
    is_back: int = Field(description='Client SomuaModelConfig.isBack; raw int32')
    is_body: int = Field(description='Client SomuaModelConfig.isBody; raw int32')
    is_ear: int = Field(description='Client SomuaModelConfig.isEar; raw int32')
    is_expression: int = Field(
        description='Client SomuaModelConfig.isExpression; raw int32'
    )
    is_hand: int = Field(description='Client SomuaModelConfig.isHand; raw int32')
    is_head: int = Field(description='Client SomuaModelConfig.isHead; raw int32')
    is_surrounding: int = Field(
        description='Client SomuaModelConfig.isSurrounding; raw int32'
    )
    is_tail: int = Field(description='Client SomuaModelConfig.isTail; raw int32')
    is_topwear: int = Field(description='Client SomuaModelConfig.isTopwear; raw int32')
    name: str = Field(description='Client SomuaModelConfig.name; raw string')
    pet_id: int = Field(description='Client SomuaModelConfig.petID; raw int32')
    prefix: str = Field(description='Client SomuaModelConfig.prefix; raw string')
    season: str = Field(description='Client SomuaModelConfig.season; raw string')
    suffix: str = Field(description='Client SomuaModelConfig.suffix; raw string')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_model'


class SomuaModel(BaseSomuaModel, ConvertToORM['SomuaModelORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaModelORM']:
        return SomuaModelORM

    def to_orm(self) -> 'SomuaModelORM':
        return SomuaModelORM(**self.model_dump())


class SomuaModelORM(BaseSomuaModel, table=True):
    pass


class BaseSomuaRanking(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    icon: int = Field(description='Client SomuaRankingConfig.icon; raw int32')
    is_falling: int = Field(
        description='Client SomuaRankingConfig.isFalling; raw int32'
    )
    level: str = Field(description='Client SomuaRankingConfig.level; raw string')
    minscore: str = Field(description='Client SomuaRankingConfig.minscore; raw string')
    name: str = Field(description='Client SomuaRankingConfig.name; raw string')
    phase: int = Field(description='Client SomuaRankingConfig.phase; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_ranking'


class SomuaRanking(BaseSomuaRanking, ConvertToORM['SomuaRankingORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaRankingORM']:
        return SomuaRankingORM

    def to_orm(self) -> 'SomuaRankingORM':
        return SomuaRankingORM(**self.model_dump())


class SomuaRankingORM(BaseSomuaRanking, table=True):
    pass


class BaseSomuaShop(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['title']
    new_msglog_id: int = Field(
        description='Client SomuaShopConfig.NewMsglogId; raw int32'
    )
    price: int = Field(description='Client SomuaShopConfig.Price; raw int32')
    describe1: str = Field(description='Client SomuaShopConfig.describe1; raw string')
    describe2: str = Field(description='Client SomuaShopConfig.describe2; raw string')
    forever: int = Field(description='Client SomuaShopConfig.forever; raw int32')
    limit: int = Field(description='Client SomuaShopConfig.limit; raw int32')
    limit_type: int = Field(description='Client SomuaShopConfig.limitType; raw int32')
    quantity: int = Field(description='Client SomuaShopConfig.quantity; raw int32')
    rewardinfo: str = Field(description='Client SomuaShopConfig.rewardinfo; raw string')
    shop_type1: int = Field(description='Client SomuaShopConfig.shopType1; raw int32')
    title: str = Field(description='Client SomuaShopConfig.title; raw string')
    userinfo: int = Field(description='Client SomuaShopConfig.userinfo; raw int32')
    value: int = Field(description='Client SomuaShopConfig.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_shop'


class SomuaShop(BaseSomuaShop, ConvertToORM['SomuaShopORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaShopORM']:
        return SomuaShopORM

    def to_orm(self) -> 'SomuaShopORM':
        return SomuaShopORM(**self.model_dump())


class SomuaShopORM(BaseSomuaShop, table=True):
    pass


class BaseSomuaStatusEffect(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['status_name']
    fx_on_get: str = Field(
        description='Client SomuaStatusEffectConfig.fxOnGet; raw string'
    )
    fx_on_trig: str = Field(
        description='Client SomuaStatusEffectConfig.fxOnTrig; raw string'
    )
    icon: int = Field(description='Client SomuaStatusEffectConfig.icon; raw int32')
    max_stack: int = Field(
        description='Client SomuaStatusEffectConfig.maxStack; raw int32'
    )
    stack_rule: str = Field(
        description='Client SomuaStatusEffectConfig.stackRule; raw string'
    )
    status_desc: str = Field(
        description='Client SomuaStatusEffectConfig.statusDesc; raw string'
    )
    status_name: str = Field(
        description='Client SomuaStatusEffectConfig.statusName; raw string'
    )
    type: int = Field(description='Client SomuaStatusEffectConfig.type; raw int32')
    value_rule: str = Field(
        description='Client SomuaStatusEffectConfig.valueRule; raw string'
    )

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_status_effect'


class SomuaStatusEffect(BaseSomuaStatusEffect, ConvertToORM['SomuaStatusEffectORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaStatusEffectORM']:
        return SomuaStatusEffectORM

    def to_orm(self) -> 'SomuaStatusEffectORM':
        return SomuaStatusEffectORM(**self.model_dump())


class SomuaStatusEffectORM(BaseSomuaStatusEffect, table=True):
    pass


class BaseSomuaTask(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    describe: str = Field(description='Client SomuaTaskConfig.describe; raw string')
    group: int = Field(description='Client SomuaTaskConfig.group; raw int32')
    period: int = Field(description='Client SomuaTaskConfig.period; raw int32')
    rewardinfo: str = Field(description='Client SomuaTaskConfig.rewardinfo; raw string')
    season: int = Field(description='Client SomuaTaskConfig.season; raw int32')
    tasktype: int = Field(description='Client SomuaTaskConfig.tasktype; raw int32')
    value: int = Field(description='Client SomuaTaskConfig.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_task'


class SomuaTask(BaseSomuaTask, ConvertToORM['SomuaTaskORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaTaskORM']:
        return SomuaTaskORM

    def to_orm(self) -> 'SomuaTaskORM':
        return SomuaTaskORM(**self.model_dump())


class SomuaTaskORM(BaseSomuaTask, table=True):
    pass


class BaseSomuaTutorial(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    img: str = Field(description='Client SomuaToturialConfig.img; raw string')
    module: str = Field(description='Client SomuaToturialConfig.module; raw string')
    page: int = Field(description='Client SomuaToturialConfig.page; raw int32')
    txt: str = Field(description='Client SomuaToturialConfig.txt; raw string')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_tutorial'


class SomuaTutorial(BaseSomuaTutorial, ConvertToORM['SomuaTutorialORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaTutorialORM']:
        return SomuaTutorialORM

    def to_orm(self) -> 'SomuaTutorialORM':
        return SomuaTutorialORM(**self.model_dump())


class SomuaTutorialORM(BaseSomuaTutorial, table=True):
    pass


class BaseSomuaWeapon(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    fx_on_hit: str = Field(description='Client SomuaWeaponConfig.fxOnHit; raw string')
    prefab: str = Field(description='Client SomuaWeaponConfig.prefab; raw string')
    shape: int = Field(description='Client SomuaWeaponConfig.shape; raw int32')
    type: int = Field(description='Client SomuaWeaponConfig.type; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'somua_weapon'


class SomuaWeapon(BaseSomuaWeapon, ConvertToORM['SomuaWeaponORM']):
    @classmethod
    def get_orm_model(cls) -> type['SomuaWeaponORM']:
        return SomuaWeaponORM

    def to_orm(self) -> 'SomuaWeaponORM':
        return SomuaWeaponORM(**self.model_dump())


class SomuaWeaponORM(BaseSomuaWeapon, table=True):
    pass


from .dango import (
    Dango,
    DangoAction,
    DangoChess,
    DangoChessStage,
    DangoGene,
    DangoGold,
    DangoGuide,
    DangoHouse,
    DangoLevel,
    DangoShop,
    DangoSlot,
    DangoStory,
    DangoTask,
)

SOMUA_RESOURCES = {
    'SomuaAchievementConfig.json': SomuaAchievement,
    'SomuaBasicAttritube.json': SomuaBasicAttribute,
    'SomuaDispatchConfig.json': SomuaDispatch,
    'SomuaEntryConfig.json': SomuaEntry,
    'SomuaGeneConfig.json': SomuaGene,
    'SomuaHouseConfig.json': SomuaHouse,
    'SomuaKeeperConfig.json': SomuaKeeper,
    'SomuaModelConfig.json': SomuaModel,
    'SomuaRankingConfig.json': SomuaRanking,
    'SomuaShopConfig.json': SomuaShop,
    'SomuaStatusEffectConfig.json': SomuaStatusEffect,
    'SomuaTaskConfig.json': SomuaTask,
    'SomuaToturialConfig.json': SomuaTutorial,
    'SomuaWeaponConfig.json': SomuaWeapon,
    'dango.json': Dango,
    'dangoAction.json': DangoAction,
    'dangoGene.json': DangoGene,
    'dangoGold.json': DangoGold,
    'dangoGuide.json': DangoGuide,
    'dangoHouse.json': DangoHouse,
    'dangoLv.json': DangoLevel,
    'dangoShop.json': DangoShop,
    'dangoSlot.json': DangoSlot,
    'dangoStory.json': DangoStory,
    'dangoTask.json': DangoTask,
    'dangochess.json': DangoChess,
    'dangochessstage.json': DangoChessStage,
}
