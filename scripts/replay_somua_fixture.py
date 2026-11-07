"""Replay the pinned official client fixture through production outputters."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from typing import cast

from seerapi_models.metadata import ApiMetadata
from seerapi_models.somua import SOMUA_RESOURCES
from seerapi_models.somua_source import validate_somua_source
from solaris.analyze import (
    analyze_result_to_db,
    analyze_result_to_json,
    analyzers_to_jsonschema,
    analyzers_to_oad,
)
from solaris.analyze.analyzers.somua import SomuaAnalyzer
from solaris.analyze.base import DataImportConfig
from solaris.analyze.settings import DataSourceDirSettings
from solaris.analyze.typing_ import JsonFormat
from solaris.parse import import_parser_classes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'packages/solaris/tests/fixtures/somua'


def replay(output: Path) -> dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    source = output / 'source'
    unity = source / 'unity'
    unity.mkdir(parents=True, exist_ok=True)
    evidence = json.loads((FIXTURE / 'client-evidence.json').read_text('utf-8'))
    for parser in import_parser_classes():
        filename = parser.parsed_config_filename()
        if filename not in SOMUA_RESOURCES:
            continue
        raw = (FIXTURE / parser.source_config_filename()).read_bytes()
        expected = evidence['tables'][filename[:-5]]
        if sha256(raw).hexdigest() != expected['sha256']:
            raise ValueError(f'Fixture checksum mismatch: {filename}')
        (unity / filename).write_text(
            json.dumps(parser().parse(raw), ensure_ascii=False), 'utf-8'
        )
    previous = DataImportConfig.SOURCE_DIR_SETTINGS
    try:
        DataImportConfig.set_source_dir(DataSourceDirSettings(BASE_DIR=source))
        results = SomuaAnalyzer().analyze()
    finally:
        DataImportConfig.set_source_dir(previous)
    metadata = ApiMetadata(
        api_url='https://api.seerapi.com',
        api_version='v1',
        generator_name='Somua fixture replay',
        generator_version='local',
        data_version=evidence['config_version'],
    )
    for json_format, directory in (
        ('split', 'data'),
        ('merged', 'merged_data'),
        ('sharded', 'sharded_data'),
    ):
        analyze_result_to_json(
            results,
            metadata=metadata,
            base_output_dir=output,
            data_output_dir=directory,
            # Names such as "赛尔豆*10000" are valid on CI Linux, not Windows.
            # Merged/sharded name indexes preserve and validate all names locally.
            json_format=cast(JsonFormat, json_format),
            output_named_data=json_format != 'split' or os.name != 'nt',
        )
    database = output / 'seerapi-data.sqlite'
    if database.exists():
        raise FileExistsError(f'Replay output must be fresh: {database}')
    analyze_result_to_db(results, metadata=metadata, db_url=f'sqlite:///{database}')
    with sqlite3.connect(database) as connection:
        validate_somua_source(connection, source)
    analyzers_to_jsonschema(
        [SomuaAnalyzer],
        metadata=metadata,
        base_output_dir=output,
        schema_output_dir='schemas',
        output_named_data=True,
    )
    analyzers_to_oad(
        [SomuaAnalyzer],
        metadata=metadata,
        base_output_dir=output,
        title='Somua fixture',
        detail_version='1.0.0',
        description='Local validation',
        output_named_data=True,
    )
    return {result.model.resource_name(): len(result.data) for result in results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(replay(parser.parse_args().output), indent=2))  # noqa: T201
