import click
import httpx

from seerapi import PageInfo
from seerapi.cli.context import CliContext
from seerapi.cli.output import (
    page_info_to_dict,
    project_fields,
    write_error,
    write_json,
)
from seerapi.cli.runner import run_async, with_client
from seerapi.cli.validation import is_valid_resource, unknown_resource_error


@click.command('list')
@click.argument('resource')
@click.option('--offset', default=0, type=int, show_default=True)
@click.option('--limit', default=20, type=int, show_default=True)
@click.option(
    '--expand/--no-expand',
    default=True,
    show_default=True,
    help='Return full resource objects in list results.',
)
@click.option(
    '--fields',
    default=None,
    help='Comma-separated fields to include for each result item.',
)
@click.pass_obj
def list_cmd(
    ctx: CliContext,
    resource: str,
    offset: int,
    limit: int,
    expand: bool,
    fields: str | None,
) -> None:
    """List resources with single-page pagination."""
    if not is_valid_resource(resource):
        write_error(unknown_resource_error(resource), exit_code=2)

    field_list = [field.strip() for field in fields.split(',')] if fields else None
    page_info = PageInfo(offset=offset, limit=limit, expand=expand)

    async def _list(client):
        paged = await client.paginated_list(resource, page_info)
        results = [
            project_fields(item.model_dump(mode='json'), field_list)
            async for item in paged.results
        ]
        return {
            'count': paged.count,
            'offset': offset,
            'limit': limit,
            'results': results,
            'next': page_info_to_dict(paged.next),
            'previous': page_info_to_dict(paged.previous),
        }

    try:
        payload = run_async(with_client(ctx, _list))
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

    write_json(payload, pretty=ctx.pretty)
