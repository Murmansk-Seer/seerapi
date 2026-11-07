"""Full resource exports share Pydantic core schemas across repeated runs."""

import json
from pathlib import Path

from seerapi_models.metadata import ApiMetadata
from seerapi_models.somua import SOMUA_RESOURCES
from solaris.analyze import (
    analyzers_to_jsonschema,
    analyzers_to_oad,
    import_analyzer_classes,
)


def test_full_schema_and_openapi_exports_can_repeat_in_one_process(
    tmp_path: Path,
) -> None:
    metadata = ApiMetadata(
        api_url='https://api.seerapi.com',
        api_version='v1',
        generator_name='solaris',
        generator_version='test',
    )
    analyzers = import_analyzer_classes()
    expected = {model.resource_name() for model in SOMUA_RESOURCES.values()}
    indexes = []
    for folder in ('first', 'second'):
        output = tmp_path / folder
        analyzers_to_jsonschema(
            analyzers,
            metadata=metadata,
            base_output_dir=output,
            schema_output_dir='schemas',
            output_named_data=True,
        )
        analyzers_to_oad(
            analyzers,
            metadata=metadata,
            base_output_dir=output,
            title='SeerAPI',
            detail_version='1.0.0',
            description='',
            output_named_data=True,
        )
        schema_index = json.loads(
            (output / 'v1/schemas/index.json').read_text(encoding='utf-8')
        )
        indexes.append(schema_index)
        for resource in expected:
            assert (output / f'v1/schemas/{resource}/$id/index.json').is_file()
        openapi = json.loads((output / 'v1/openapi.json').read_text(encoding='utf-8'))
        assert all(f'v1/{resource}/{{id}}' in openapi['paths'] for resource in expected)
    assert indexes[0] == indexes[1]
