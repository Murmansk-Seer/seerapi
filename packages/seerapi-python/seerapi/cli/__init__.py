import click

from seerapi.cli.commands.describe import describe_cmd
from seerapi.cli.commands.get import get_cmd
from seerapi.cli.commands.get_by_name import get_by_name_cmd
from seerapi.cli.commands.list_cmd import list_cmd
from seerapi.cli.commands.resources import resources_cmd
from seerapi.cli.commands.skill import skill_group
from seerapi.cli.context import CliContext


@click.group(
    invoke_without_command=True,
    context_settings={'help_option_names': ['-h', '--help']},
)
@click.option(
    '--hostname',
    default='api.seerapi.com',
    envvar='SEERAPI_HOSTNAME',
    show_default=True,
    help='API hostname.',
)
@click.option(
    '--scheme',
    default='https',
    envvar='SEERAPI_SCHEME',
    show_default=True,
    help='API URL scheme.',
)
@click.option(
    '--version-path',
    default='v1',
    show_default=True,
    help='API version path segment.',
)
@click.option(
    '--pretty',
    is_flag=True,
    default=False,
    help='Pretty-print JSON output.',
)
@click.version_option(
    None,
    '-V',
    '--version',
    package_name='seerapi',
    prog_name='seerapi',
)
@click.pass_context
def cli_main(
    ctx: click.Context,
    hostname: str,
    scheme: str,
    version_path: str,
    pretty: bool,
) -> None:
    """SeerAPI command-line client."""
    if not isinstance(ctx.obj, CliContext):
        ctx.obj = CliContext(
            hostname=hostname,
            scheme=scheme,
            version_path=version_path,
            pretty=pretty,
        )
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli_main.add_command(resources_cmd)
cli_main.add_command(describe_cmd)
cli_main.add_command(get_cmd)
cli_main.add_command(list_cmd)
cli_main.add_command(get_by_name_cmd)
cli_main.add_command(skill_group)
