"""Somua filter layout verified against GameLogic 20261119215136."""

from typing import TypedDict, cast

from ..base import BaseParser
from .somua import _parse


class SomuaFilterInfo(TypedDict):
    category: int
    entrys: str
    icon: str
    id: int
    mutual: str
    name: str


class SomuaFilterConfig(TypedDict):
    data: list[SomuaFilterInfo]


class SomuaFilterParser(BaseParser[SomuaFilterConfig]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'SomuaFilterConfig.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'SomuaFilterConfig.json'

    def parse(self, data: bytes) -> SomuaFilterConfig:
        return cast(
            SomuaFilterConfig,
            _parse(
                data,
                (
                    ('category', 'int32'),
                    ('entrys', 'string'),
                    ('icon', 'string'),
                    ('id', 'int32'),
                    ('mutual', 'string'),
                    ('name', 'string'),
                ),
            ),
        )
