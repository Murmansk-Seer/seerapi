from typing import cast

import click
import httpx

from seerapi._model_map import MODEL_MAP
from seerapi._typing import ModelName
from seerapi.cli.context import CliContext
from seerapi.cli.output import filter_schema_fields, write_error, write_json
from seerapi.cli.runner import run_async, with_client
from seerapi.cli.schema import SchemaScope, fetch_schema
from seerapi.cli.validation import (
    NAMED_MODEL_NAMES,
    is_named_resource,
    is_valid_resource,
    unknown_resource_error,
)


@click.command('describe')
@click.argument('resource')
@click.option(
    '--scope',
    type=click.Choice(['item', 'list', 'name'], case_sensitive=False),
    default='item',
    show_default=True,
    help=(
        'Which schema to fetch: item (/$id), list (resource collection), '
        'or name (/$name NamedData wrapper).'
    ),
)
@click.option(
    '--fields',
    default=None,
    help='Comma-separated top-level schema fields to include.',
)
@click.pass_obj
def describe_cmd(
    ctx: CliContext,
    resource: str,
    scope: str,
    fields: str | None,
) -> None:
    """Show JSON Schema and supported operations for a resource."""
    if not is_valid_resource(resource):
        write_error(unknown_resource_error(resource), exit_code=2)

    schema_scope = cast(SchemaScope, scope.lower())
    if schema_scope == 'name' and not is_named_resource(resource):
        write_error(
            {
                'error': 'resource does not support name lookup',
                'resource': resource,
                'hint': 'use --scope item or list, or pick a NamedModel resource',
            },
            exit_code=2,
        )

    model_type = MODEL_MAP[cast(ModelName, resource)]
    field_list = [field.strip() for field in fields.split(',')] if fields else None

    async def _describe(client):
        return await fetch_schema(client, cast(ModelName, resource), scope=schema_scope)

    try:
        schema_url, schema = run_async(with_client(ctx, _describe))
    except httpx.HTTPStatusError as exc:
        write_error(
            {
                'error': str(exc),
                'status': exc.response.status_code,
                'url': str(exc.request.url),
            }
        )
    except ValueError as exc:
        write_error({'error': str(exc)}, exit_code=2)

    payload = {
        'resource': resource,
        'model': model_type.__name__,
        'supports_name_lookup': resource in NAMED_MODEL_NAMES,
        'operations': {
            'get': True,
            'list': True,
            'get_by_name': resource in NAMED_MODEL_NAMES,
        },
        'schema_scope': schema_scope,
        'schema_url': schema_url,
        'schema': filter_schema_fields(schema, field_list),
    }
    write_json(payload, pretty=ctx.pretty)
