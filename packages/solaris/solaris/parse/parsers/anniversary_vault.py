from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class AnniversaryVaultInfo(TypedDict):
    commodity: str
    id: int
    mintmarkNum: int
    needID: int
    needNum: int
    needtype: int
    page: int
    petinfo: str
    price: int
    quantity: int
    tab: int
    unique: int
    userInfoId: int


class _AnniversaryVaultData(TypedDict):
    item: list[AnniversaryVaultInfo]


class AnniversaryVaultParser(BaseParser[_AnniversaryVaultData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'AnniversaryVault.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'AnniversaryVault.json'

    def parse(self, data: bytes) -> _AnniversaryVaultData:
        reader = BytesReader(data)
        result: _AnniversaryVaultData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            item: AnniversaryVaultInfo = {
                'commodity': reader.ReadUTFBytesWithLength(),
                'id': reader.ReadSignedInt(),
                'mintmarkNum': reader.ReadSignedInt(),
                'needID': reader.ReadSignedInt(),
                'needNum': reader.ReadSignedInt(),
                'needtype': reader.ReadSignedInt(),
                'page': reader.ReadSignedInt(),
                'petinfo': reader.ReadUTFBytesWithLength(),
                'price': reader.ReadSignedInt(),
                'quantity': reader.ReadSignedInt(),
                'tab': reader.ReadSignedInt(),
                'unique': reader.ReadSignedInt(),
                'userInfoId': reader.ReadSignedInt(),
            }
            result['item'].append(item)
        return result
