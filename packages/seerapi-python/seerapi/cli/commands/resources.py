import click

from seerapi._model_map import MODEL_MAP
from seerapi.cli.context import CliContext
from seerapi.cli.output import write_json
from seerapi.cli.validation import NAMED_MODEL_NAMES


@click.command('resources')
@click.pass_obj
def resources_cmd(ctx: CliContext) -> None:
    """List all available API resources."""
    items = [
        {
            'name': name,
            'model': model_type.__name__,
            'supports_name_lookup': name in NAMED_MODEL_NAMES,
        }
        for name, model_type in sorted(MODEL_MAP.items())
    ]
    write_json(items, pretty=ctx.pretty)
