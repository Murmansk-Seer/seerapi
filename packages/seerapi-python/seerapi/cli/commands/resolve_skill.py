import click
import httpx

from seerapi.cli.context import CliContext
from seerapi.cli.output import project_fields, write_error, write_json
from seerapi.cli.runner import run_async, with_client


@click.command('resolve-skill')
@click.argument('skill_id', type=int)
@click.option(
    '--fields',
    default=None,
    help='Comma-separated top-level fields to include in the output.',
)
@click.pass_obj
def resolve_skill_cmd(
    ctx: CliContext,
    skill_id: int,
    fields: str | None,
) -> None:
    """Resolve a normal skill or a composite runtime skill-stone ID."""

    field_list = [field.strip() for field in fields.split(',')] if fields else None

    async def _resolve(client):
        return await client.resolve_skill(skill_id)

    try:
        resolved = run_async(with_client(ctx, _resolve))
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

    data = project_fields(resolved.model_dump(), field_list)
    write_json(data, pretty=ctx.pretty)
