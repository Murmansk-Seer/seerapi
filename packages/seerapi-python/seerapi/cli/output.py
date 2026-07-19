import json
import sys
from typing import Any, NoReturn

import click

from seerapi._models import PageInfo


def write_json(data: Any, *, pretty: bool = False) -> None:
    if pretty:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(json.dumps(data, ensure_ascii=False, separators=(',', ':')))


def write_error(error: dict[str, Any], *, exit_code: int = 1) -> NoReturn:
    click.echo(json.dumps(error, ensure_ascii=False, separators=(',', ':')), err=True)
    sys.exit(exit_code)


def page_info_to_dict(page_info: PageInfo | None) -> dict[str, int | bool] | None:
    if page_info is None:
        return None
    return {
        'offset': page_info.offset,
        'limit': page_info.limit,
        'expand': page_info.expand,
    }


def project_fields(data: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
    if not fields:
        return data
    return {key: data[key] for key in fields if key in data}


def filter_schema_fields(
    schema: dict[str, Any], fields: list[str] | None
) -> dict[str, Any]:
    if not fields:
        return schema

    filtered = dict(schema)
    properties = schema.get('properties')
    if isinstance(properties, dict):
        filtered['properties'] = {
            key: value for key, value in properties.items() if key in fields
        }
        required = schema.get('required')
        if isinstance(required, list):
            filtered['required'] = [key for key in required if key in fields]
        return filtered

    all_of = schema.get('allOf')
    if isinstance(all_of, list):
        filtered['allOf'] = [
            filter_schema_fields(item, fields)
            if isinstance(item, dict) and 'properties' in item
            else item
            for item in all_of
        ]
    return filtered
