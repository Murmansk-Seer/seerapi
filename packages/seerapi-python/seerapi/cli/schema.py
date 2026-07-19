from typing import Any, Literal

from seerapi import SeerAPI
from seerapi._typing import ModelName

SchemaScope = Literal['item', 'list', 'name']

_SCOPE_PATH: dict[SchemaScope, str] = {
    'item': '/$id',
    'list': '',
    'name': '/$name',
}


def build_schema_path(resource: ModelName, scope: SchemaScope) -> str:
    return f'/schemas/{resource}{_SCOPE_PATH[scope]}'


async def fetch_schema(
    client: SeerAPI,
    resource: ModelName,
    *,
    scope: SchemaScope = 'item',
) -> tuple[str, dict[str, Any]]:
    path = build_schema_path(resource, scope)
    schema_response = await client._client.get(path)
    schema_response.raise_for_status()
    schema = schema_response.json()
    if not isinstance(schema, dict):
        raise ValueError(f'Schema at {path} is not a JSON object')

    return str(schema_response.url), schema
