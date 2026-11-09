"""Independent Somua and legacy dango resources; numeric values are unscaled."""

from typing import ClassVar

from sqlalchemy import JSON
from sqlmodel import Field

from seerapi_models.build_model import BaseResModel, ConvertToORM


class BaseDango(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name', 'gene']
    describe: str = Field(description='Client dango.describe; raw string')
    gene: str = Field(description='Client dango.gene; raw string')
    grade: int = Field(description='Client dango.grade; raw int32')
    name: str = Field(description='Client dango.name; raw string')
    pet_id: int = Field(description='Client dango.petID; raw int32')
    skin: str = Field(description='Client dango.skin; raw string')
    value: int = Field(description='Client dango.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango'


class Dango(BaseDango, ConvertToORM['DangoORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoORM']:
        return DangoORM

    def to_orm(self) -> 'DangoORM':
        return DangoORM(**self.model_dump())


class DangoORM(BaseDango, table=True):
    pass


class BaseDangoAction(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    action: str = Field(description='Client dangoAction.action; raw string')
    action_team: int = Field(description='Client dangoAction.actionTeam; raw int32')
    dango_id: list[int] | None = Field(
        sa_type=JSON, description='Client dangoAction.dangoID; raw int32[]'
    )
    describ: str = Field(description='Client dangoAction.describ; raw string')
    limit_dango: int = Field(description='Client dangoAction.limitDango; raw int32')
    limit_type: int = Field(description='Client dangoAction.limitType; raw int32')
    value: int = Field(description='Client dangoAction.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_action'


class DangoAction(BaseDangoAction, ConvertToORM['DangoActionORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoActionORM']:
        return DangoActionORM

    def to_orm(self) -> 'DangoActionORM':
        return DangoActionORM(**self.model_dump())


class DangoActionORM(BaseDangoAction, table=True):
    pass


class BaseDangoGene(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    gene_id: int = Field(description='Client dangoGene.geneID; raw int32')
    name: str = Field(description='Client dangoGene.name; raw string')
    skinbaby: str = Field(description='Client dangoGene.skinbaby; raw string')
    skinteen: str = Field(description='Client dangoGene.skinteen; raw string')
    value: int = Field(description='Client dangoGene.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_gene'


class DangoGene(BaseDangoGene, ConvertToORM['DangoGeneORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoGeneORM']:
        return DangoGeneORM

    def to_orm(self) -> 'DangoGeneORM':
        return DangoGeneORM(**self.model_dump())


class DangoGeneORM(BaseDangoGene, table=True):
    pass


class BaseDangoGold(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    dango_gold: int = Field(description='Client dangoGold.dangoGold; raw int32')
    dango_num_max: int = Field(description='Client dangoGold.dangoNumMax; raw int32')
    dango_num_mix: int = Field(description='Client dangoGold.dangoNumMix; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_gold'


class DangoGold(BaseDangoGold, ConvertToORM['DangoGoldORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoGoldORM']:
        return DangoGoldORM

    def to_orm(self) -> 'DangoGoldORM':
        return DangoGoldORM(**self.model_dump())


class DangoGoldORM(BaseDangoGold, table=True):
    pass


class BaseDangoGuide(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['titile']
    dango_movie: str = Field(description='Client dangoGuide.dangoMovie; raw string')
    describe: str = Field(description='Client dangoGuide.describe; raw string')
    reward: str = Field(description='Client dangoGuide.reward; raw string')
    titile: str = Field(description='Client dangoGuide.titile; raw string')
    type: int = Field(description='Client dangoGuide.type; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_guide'


class DangoGuide(BaseDangoGuide, ConvertToORM['DangoGuideORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoGuideORM']:
        return DangoGuideORM

    def to_orm(self) -> 'DangoGuideORM':
        return DangoGuideORM(**self.model_dump())


class DangoGuideORM(BaseDangoGuide, table=True):
    pass


class BaseDangoHouse(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    limit_cost: int = Field(description='Client dangoHouse.limitCost; raw int32')
    name: str = Field(description='Client dangoHouse.name; raw string')
    room_id: int = Field(description='Client dangoHouse.roomID; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_house'


class DangoHouse(BaseDangoHouse, ConvertToORM['DangoHouseORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoHouseORM']:
        return DangoHouseORM

    def to_orm(self) -> 'DangoHouseORM':
        return DangoHouseORM(**self.model_dump())


class DangoHouseORM(BaseDangoHouse, table=True):
    pass


class BaseDangoLevel(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    benefit1: int = Field(description='Client dangoLv.benefit1; raw int32')
    benefit2: int = Field(description='Client dangoLv.benefit2; raw int32')
    benefit3: int = Field(description='Client dangoLv.benefit3; raw int32')
    dango_task: list[int] | None = Field(
        sa_type=JSON, description='Client dangoLv.dangoTask; raw int32[]'
    )
    describe1: str = Field(description='Client dangoLv.describe1; raw string')
    describe2: str = Field(description='Client dangoLv.describe2; raw string')
    describe3: str = Field(description='Client dangoLv.describe3; raw string')
    minor_num: int = Field(description='Client dangoLv.minorNum; raw int32')
    reward: int = Field(description='Client dangoLv.reward; raw int32')
    task_num: int = Field(description='Client dangoLv.taskNum; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_level'


class DangoLevel(BaseDangoLevel, ConvertToORM['DangoLevelORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoLevelORM']:
        return DangoLevelORM

    def to_orm(self) -> 'DangoLevelORM':
        return DangoLevelORM(**self.model_dump())


class DangoLevelORM(BaseDangoLevel, table=True):
    pass


class BaseDangoShop(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['title']
    new_msglog_id: int = Field(description='Client dangoShop.NewMsglogId; raw int32')
    price: int = Field(description='Client dangoShop.Price; raw int32')
    describe1: str = Field(description='Client dangoShop.describe1; raw string')
    describe2: str = Field(description='Client dangoShop.describe2; raw string')
    forever: int = Field(description='Client dangoShop.forever; raw int32')
    limit: int = Field(description='Client dangoShop.limit; raw int32')
    quantity: int = Field(description='Client dangoShop.quantity; raw int32')
    rewardinfo: str = Field(description='Client dangoShop.rewardinfo; raw string')
    shop_type1: int = Field(description='Client dangoShop.shopType1; raw int32')
    shop_type2: int = Field(description='Client dangoShop.shopType2; raw int32')
    title: str = Field(description='Client dangoShop.title; raw string')
    userinfo: int = Field(description='Client dangoShop.userinfo; raw int32')
    value: int = Field(description='Client dangoShop.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_shop'


class DangoShop(BaseDangoShop, ConvertToORM['DangoShopORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoShopORM']:
        return DangoShopORM

    def to_orm(self) -> 'DangoShopORM':
        return DangoShopORM(**self.model_dump())


class DangoShopORM(BaseDangoShop, table=True):
    pass


class BaseDangoSlot(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['name']
    name: str = Field(description='Client dangoSlot.name; raw string')
    pet_id: int = Field(description='Client dangoSlot.petID; raw int32')
    value: int = Field(description='Client dangoSlot.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_slot'


class DangoSlot(BaseDangoSlot, ConvertToORM['DangoSlotORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoSlotORM']:
        return DangoSlotORM

    def to_orm(self) -> 'DangoSlotORM':
        return DangoSlotORM(**self.model_dump())


class DangoSlotORM(BaseDangoSlot, table=True):
    pass


class BaseDangoStory(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    dango_id: int = Field(description='Client dangoStory.dangoID; raw int32')
    dango_task: int = Field(description='Client dangoStory.dangoTask; raw int32')
    describe: str = Field(description='Client dangoStory.describe; raw string')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_story'


class DangoStory(BaseDangoStory, ConvertToORM['DangoStoryORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoStoryORM']:
        return DangoStoryORM

    def to_orm(self) -> 'DangoStoryORM':
        return DangoStoryORM(**self.model_dump())


class DangoStoryORM(BaseDangoStory, table=True):
    pass


class BaseDangoTask(BaseResModel):
    __name_fields__: ClassVar[list[str]] = ['title']
    new_msglog_id: int = Field(description='Client dangoTask.NewMsglogId; raw int32')
    describe: str = Field(description='Client dangoTask.describe; raw string')
    limit: int = Field(description='Client dangoTask.limit; raw int32')
    planet: str = Field(description='Client dangoTask.planet; raw string')
    rewardinfo: int = Field(description='Client dangoTask.rewardinfo; raw int32')
    task_skin: str = Field(description='Client dangoTask.taskSkin; raw string')
    task_team: int = Field(description='Client dangoTask.taskTeam; raw int32')
    tasktype: int = Field(description='Client dangoTask.tasktype; raw int32')
    time: int = Field(description='Client dangoTask.time; raw int32')
    title: str = Field(description='Client dangoTask.title; raw string')
    value: int = Field(description='Client dangoTask.value; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_task'


class DangoTask(BaseDangoTask, ConvertToORM['DangoTaskORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoTaskORM']:
        return DangoTaskORM

    def to_orm(self) -> 'DangoTaskORM':
        return DangoTaskORM(**self.model_dump())


class DangoTaskORM(BaseDangoTask, table=True):
    pass


class BaseDangoChess(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    guide_card: str = Field(description='Client dangochess.GuideCard; raw string')
    cardid: str = Field(description='Client dangochess.cardid; raw string')
    chapterid: int = Field(description='Client dangochess.chapterid; raw int32')
    dango_id: int = Field(description='Client dangochess.dangoID; raw int32')
    firstreward: str = Field(description='Client dangochess.firstreward; raw string')
    stageid: int = Field(description='Client dangochess.stageid; raw int32')
    starttime: str = Field(description='Client dangochess.starttime; raw string')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_chess'


class DangoChess(BaseDangoChess, ConvertToORM['DangoChessORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoChessORM']:
        return DangoChessORM

    def to_orm(self) -> 'DangoChessORM':
        return DangoChessORM(**self.model_dump())


class DangoChessORM(BaseDangoChess, table=True):
    pass


class BaseDangoChessStage(BaseResModel):
    __name_fields__: ClassVar[list[str]] = []
    chapterid: int = Field(description='Client dangochessstage.chapterid; raw int32')
    hangid: int = Field(description='Client dangochessstage.hangid; raw int32')
    lieid1: int = Field(description='Client dangochessstage.lieid1; raw int32')
    lieid2: int = Field(description='Client dangochessstage.lieid2; raw int32')
    lieid3: int = Field(description='Client dangochessstage.lieid3; raw int32')
    lieid4: int = Field(description='Client dangochessstage.lieid4; raw int32')
    lieid5: int = Field(description='Client dangochessstage.lieid5; raw int32')
    lieid6: int = Field(description='Client dangochessstage.lieid6; raw int32')
    lieid7: int = Field(description='Client dangochessstage.lieid7; raw int32')
    lieid8: int = Field(description='Client dangochessstage.lieid8; raw int32')
    lieid9: int = Field(description='Client dangochessstage.lieid9; raw int32')
    stageid: int = Field(description='Client dangochessstage.stageid; raw int32')

    @classmethod
    def resource_name(cls) -> str:
        return 'dango_chess_stage'


class DangoChessStage(BaseDangoChessStage, ConvertToORM['DangoChessStageORM']):
    @classmethod
    def get_orm_model(cls) -> type['DangoChessStageORM']:
        return DangoChessStageORM

    def to_orm(self) -> 'DangoChessStageORM':
        return DangoChessStageORM(**self.model_dump())


class DangoChessStageORM(BaseDangoChessStage, table=True):
    pass
