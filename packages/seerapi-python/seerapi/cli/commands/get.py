import click
import httpx

from seerapi.cli.context import CliContext
from seerapi.cli.output import project_fields, write_error, write_json
from seerapi.cli.runner import run_async, with_client
from seerapi.cli.validation import is_valid_resource, unknown_resource_error


@click.command('get')
@click.argument('resource')
@click.argument('id', type=int)
@click.option(
    '--fields',
    default=None,
    help='Comma-separated fields to include in the output.',
)
@click.pass_obj
def get_cmd(ctx: CliContext, resource: str, id: int, fields: str | None) -> None:
    """Get a single resource by ID."""
    if not is_valid_resource(resource):
        write_error(unknown_resource_error(resource), exit_code=2)

    field_list = [field.strip() for field in fields.split(',')] if fields else None

    async def _get(client):
        return await client.get(resource, id)

    try:
        model = run_async(with_client(ctx, _get))
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

    data = project_fields(model.model_dump(mode='json'), field_list)
    write_json(data, pretty=ctx.pretty)
