"""Fail-closed checks shared by intermediate and final database publishers."""

import json
from pathlib import Path
import sqlite3

from .somua import SOMUA_RESOURCES


def load_somua_source(source: Path) -> dict:
    result = {}
    for filename, model in SOMUA_RESOURCES.items():
        payload = json.loads((source / 'unity' / filename).read_text('utf-8'))
        if set(payload) != {'data'} or not isinstance(payload['data'], list):
            raise ValueError(f'Invalid Somua source: {filename}')
        rows = {}
        for row in payload['data']:
            if set(row) != set(model.model_fields):
                raise ValueError(f'Somua field drift: {filename}')
            item = model.model_validate(row, strict=True)
            if item.id in rows:
                raise ValueError(f'Duplicate Somua ID: {filename}/{item.id}')
            rows[item.id] = item.model_dump()
        result[model] = rows
    return result


def validate_somua_source(connection: sqlite3.Connection, source: Path) -> None:
    for model, expected in load_somua_source(source).items():
        table = model.resource_name()
        columns = list(model.model_fields)
        query = ', '.join(f'"{field}"' for field in columns)
        actual = {}
        for values in connection.execute(f'SELECT {query} FROM "{table}"'):
            row = dict(zip(columns, values))
            for field, value in row.items():
                if isinstance(value, str) and model.model_fields[field].annotation == (
                    list[int] | None
                ):
                    row[field] = json.loads(value)
            item = model.model_validate(row, strict=True)
            if item.id in actual:
                raise ValueError(f'Duplicate database Somua ID: {table}/{item.id}')
            actual[item.id] = item.model_dump()
        if actual != expected:
            raise ValueError(f'{table} differs from frozen official source')
