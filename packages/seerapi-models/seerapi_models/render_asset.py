from pydantic import BaseModel
from sqlmodel import Field, SQLModel


class RenderAssetManifest(BaseModel):
    """A release-owned rendering asset revision published with SeerAPI data."""

    asset_kind: str = Field(description="渲染素材种类")
    asset_key: str = Field(description="素材在种类中的稳定键")
    sha256: str = Field(description="素材 PNG 的 SHA-256；不可用素材为空字符串")
    release_revision: str = Field(description="产生该素材事实的数据发布版本")
    available: bool = Field(description="该发布物是否含有可用素材")
    source: str = Field(description="构建期素材来源说明")


class RenderAssetManifestORM(RenderAssetManifest, SQLModel, table=True):
    __tablename__ = "render_asset_manifest"  # type: ignore

    asset_kind: str = Field(primary_key=True)
    asset_key: str = Field(primary_key=True)
    updated_at: float = Field(description="构建写入时间戳")
