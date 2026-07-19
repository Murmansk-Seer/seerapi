import click
import httpx

from seerapi.cli.context import CliContext
from seerapi.cli.output import write_error, write_json
from seerapi.cli.runner import run_async, with_client
from seerapi.cli.validation import (
    is_named_resource,
    is_valid_resource,
    unknown_resource_error,
)


@click.command('get-by-name')
@click.argument('resource')
@click.argument('name')
@click.pass_obj
def get_by_name_cmd(ctx: CliContext, resource: str, name: str) -> None:
    """Get resources by name (NamedModel resources only)."""
    if not is_valid_resource(resource):
        write_error(unknown_resource_error(resource), exit_code=2)

    if not is_named_resource(resource):
        write_error(
            {
                'error': 'resource does not support name lookup',
                'resource': resource,
                'hint': 'run seerapi resources and filter supports_name_lookup=true',
            },
            exit_code=2,
        )

    async def _get_by_name(client):
        return await client.get_by_name(resource, name)

    try:
        named_data = run_async(with_client(ctx, _get_by_name))
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
        str(resource_id): item.model_dump(mode='json')
        for resource_id, item in named_data.data.items()
    }
    write_json(payload, pretty=ctx.pretty)
