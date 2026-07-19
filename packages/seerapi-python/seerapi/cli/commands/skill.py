from pathlib import Path

import click

from seerapi.cli.context import CliContext
from seerapi.cli.output import write_error, write_json
from seerapi.cli.skill import SKILL_NAME, get_skill_source_dir, install_skill


@click.group('skill', invoke_without_command=True)
@click.pass_context
def skill_group(ctx: click.Context) -> None:
    """Show and install the bundled agent skill."""
    if ctx.invoked_subcommand is None:
        source_dir = get_skill_source_dir()
        if not source_dir.is_dir():
            write_error(
                {
                    'error': 'skill source directory not found',
                    'path': str(source_dir),
                },
                exit_code=2,
            )

        cli_ctx = ctx.obj if isinstance(ctx.obj, CliContext) else CliContext()
        write_json(
            {
                'name': SKILL_NAME,
                'source_path': str(source_dir),
                'install': (
                    'seerapi skill install --target <your-agent-skills-dir>/seerapi-cli'
                ),
                'hint': (
                    'Copy or install into your AI agent skills directory. '
                    'Set SEERAPI_SKILL_DIR to avoid passing --target each time.'
                ),
            },
            pretty=cli_ctx.pretty,
        )


@skill_group.command('path')
@click.pass_obj
def skill_path_cmd(ctx: CliContext) -> None:
    """Print the bundled skill source directory."""
    source_dir = get_skill_source_dir()
    if not source_dir.is_dir():
        write_error(
            {
                'error': 'skill source directory not found',
                'path': str(source_dir),
            },
            exit_code=2,
        )
    write_json({'path': str(source_dir)}, pretty=ctx.pretty)


@skill_group.command('install')
@click.option(
    '--target',
    type=click.Path(file_okay=False, path_type=Path),
    envvar='SEERAPI_SKILL_DIR',
    required=True,
    help=(
        'Destination skills directory. Use the parent skills folder '
        '(.../skills) or the final .../skills/seerapi-cli path.'
    ),
)
@click.pass_obj
def skill_install_cmd(ctx: CliContext, target: Path) -> None:
    """Copy the skill into your agent skills directory."""
    try:
        destination = install_skill(target_dir=target)
    except FileNotFoundError as exc:
        write_error({'error': str(exc)}, exit_code=2)

    write_json(
        {
            'installed': True,
            'name': SKILL_NAME,
            'target_path': str(destination),
        },
        pretty=ctx.pretty,
    )
