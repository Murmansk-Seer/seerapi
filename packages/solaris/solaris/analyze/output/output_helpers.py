"""Shared helpers for schema and data output implementations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from pydantic import BaseModel, Field, create_model

from seerapi_models.common import ApiResourceList, NamedResourceRef
from solaris.analyze.typing_ import TResModelRequiredId

DataMap: TypeAlias = Mapping[int, TResModelRequiredId]


def calc_hash(data: str | bytes) -> str:
    import anycrc

    crc32 = anycrc.Model('CRC32')
    if isinstance(data, str):
        data = data.encode('utf-8')
    return format(crc32.calc(data), 'x')


def create_index_model(name: str, data: dict[str, Any]) -> type[BaseModel]:
    return create_model(
        name,
        **{
            key: (str, Field(field_title_generator=lambda key, __: f'{key} Path'))
            for key in data
        },  # type: ignore
    )


def generate_api_resource_list(
    data: DataMap[TResModelRequiredId],
) -> ApiResourceList:
    return ApiResourceList(
        count=len(data),
        results=[
            NamedResourceRef.from_res_name(
                id=item.id,
                resource_name=item.resource_name(),
                name=getattr(item, 'name', None),
            )
            for item in data.values()
        ],
    )


def get_name_fields(model: type) -> list[str]:
    """Return model fields that participate in name lookup."""
    return getattr(model, '__name_fields__', ['name'])


def get_primary_name_field(model: type) -> str:
    return get_name_fields(model)[0]


def is_named_model(model: type) -> bool:
    return any(field in model.model_fields for field in get_name_fields(model))
