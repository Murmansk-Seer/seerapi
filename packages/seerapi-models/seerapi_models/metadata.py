from datetime import datetime, timezone

from pydantic import BaseModel
from sqlmodel import Field, SQLModel


def _now_utc() -> datetime:
    """生成带 UTC 时区的当前时间。

    ORM 的 datetime 列要求带时区信息，naive datetime 会在写库时
    抛出 ``Datetime values must have timezone information``。
    """
    return datetime.now(timezone.utc)


class ApiMetadata(BaseModel):
    api_url: str = Field(description='当前API的URL')
    api_version: str = Field(description='API版本')
    generator_name: str = Field(description='生成器名称')
    generator_version: str = Field(description='生成器版本')
    generate_time: datetime = Field(
        default_factory=_now_utc,
        description='生成时间',
    )
    data_source: str = Field(
        default='',
        description='数据源，可填写git仓库地址或url',
    )
    data_version: str = Field(
        default='',
        description='数据版本',
    )
    patch_source: str = Field(
        default='',
        description='补丁源，可填写git仓库地址或url',
    )
    patch_version: str = Field(
        default='',
        description='补丁版本',
    )

    def to_orm(self) -> 'ApiMetadataORM':
        return ApiMetadataORM(
            api_url=self.api_url,
            api_version=self.api_version,
            generator_name=self.generator_name,
            generator_version=self.generator_version,
            generate_time=self.generate_time,
            data_source=self.data_source,
            data_version=self.data_version,
            patch_source=self.patch_source,
            patch_version=self.patch_version,
        )


class ApiMetadataORM(ApiMetadata, SQLModel, table=True):
    __tablename__ = 'api_metadata'  # type: ignore
    id: int | None = Field(default=None, description='ID', primary_key=True)
