import json

from click.testing import CliRunner
import httpx
import pytest

from seerapi._model_map import MODEL_MAP
from seerapi.cli import cli_main
from seerapi.cli.context import CliContext


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def error_code_item() -> dict[str, object]:
    return {'id': 1, 'name': 'test_error', 'message': 'test message'}


@pytest.fixture
def error_code_schema() -> dict[str, object]:
    return {
        'allOf': [
            {
                'type': 'object',
                'title': 'ErrorCode',
                'properties': {
                    'id': {'type': 'integer'},
                    'name': {'type': 'string'},
                    'message': {'type': 'string'},
                },
                'required': ['id', 'name', 'message'],
            }
        ]
    }


@pytest.fixture
def list_ref_response(error_code_item: dict[str, object]) -> dict[str, object]:
    return {
        'count': 1234,
        'next': 'https://api.seerapi.com/v1/error_code/?offset=20&limit=20&expand=true',
        'previous': None,
        'first': 'https://api.seerapi.com/v1/error_code/?offset=0&limit=20&expand=true',
        'last': None,
        'results': [error_code_item],
    }


def _make_describe_transport(
    error_code_schema: dict[str, object],
) -> httpx.MockTransport:
    list_schema = {
        'allOf': [
            {
                '$ref': 'https://api.seerapi.com/v1/schemas/common/api_resource_list',
                'x-model-name': 'error_code',
            }
        ]
    }
    name_schema = {
        'type': 'object',
        'properties': {
            'data': {'$ref': 'https://api.seerapi.com/v1/schemas/common/named_data'}
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith('/schemas/error_code/$id'):
            return httpx.Response(200, json=error_code_schema)
        if path.endswith('/schemas/error_code/$name'):
            return httpx.Response(200, json=name_schema)
        if path.rstrip('/').endswith('/schemas/error_code'):
            return httpx.Response(200, json=list_schema)
        raise AssertionError(f'unexpected request: {request.url}')

    return httpx.MockTransport(handler)


def _invoke(
    runner: CliRunner,
    args: list[str],
    transport: httpx.MockTransport,
) -> object:
    ctx = CliContext(transport=transport)
    return runner.invoke(cli_main, args, obj=ctx)


def test_resources_outputs_all_models(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['resources'])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == len(MODEL_MAP)
    pet = next(item for item in payload if item['name'] == 'pet')
    assert pet['model'] == 'Pet'
    assert pet['supports_name_lookup'] is True
    peak_pool = next(item for item in payload if item['name'] == 'peak_pool')
    assert peak_pool['supports_name_lookup'] is False


def test_describe_known_resource(
    runner: CliRunner,
    error_code_schema: dict[str, object],
) -> None:
    result = _invoke(
        runner,
        ['describe', 'error_code'],
        _make_describe_transport(error_code_schema),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['resource'] == 'error_code'
    assert payload['model'] == 'ErrorCode'
    assert payload['operations']['get_by_name'] is True
    assert payload['schema_scope'] == 'item'
    assert payload['schema_url'].endswith('/schemas/error_code/$id')
    assert 'allOf' in payload['schema']


def test_describe_with_fields(
    runner: CliRunner,
    error_code_schema: dict[str, object],
) -> None:
    result = _invoke(
        runner,
        ['describe', 'error_code', '--fields', 'id,name'],
        _make_describe_transport(error_code_schema),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    properties = payload['schema']['allOf'][0]['properties']
    assert set(properties) == {'id', 'name'}


def test_describe_scope_list(
    runner: CliRunner,
    error_code_schema: dict[str, object],
) -> None:
    result = _invoke(
        runner,
        ['describe', 'error_code', '--scope', 'list'],
        _make_describe_transport(error_code_schema),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['schema_scope'] == 'list'
    assert payload['schema_url'].rstrip('/').endswith('/schemas/error_code')


def test_describe_scope_name(
    runner: CliRunner,
    error_code_schema: dict[str, object],
) -> None:
    result = _invoke(
        runner,
        ['describe', 'error_code', '--scope', 'name'],
        _make_describe_transport(error_code_schema),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['schema_scope'] == 'name'
    assert payload['schema_url'].endswith('/schemas/error_code/$name')
    assert 'data' in payload['schema']['properties']


def test_describe_scope_name_non_named(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['describe', 'peak_pool', '--scope', 'name'])
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload['error'] == 'resource does not support name lookup'


def test_unknown_resource_exit_code(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['get', 'foo', '1'])
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload['error'] == 'unknown resource'
    assert payload['resource'] == 'foo'


def test_get_resource(
    runner: CliRunner,
    error_code_item: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/error_code/1'):
            return httpx.Response(200, json=error_code_item)
        raise AssertionError(f'unexpected request: {request.url}')

    result = _invoke(runner, ['get', 'error_code', '1'], httpx.MockTransport(handler))
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['id'] == 1
    assert payload['name'] == 'test_error'


def test_get_with_fields(
    runner: CliRunner,
    error_code_item: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=error_code_item)

    result = _invoke(
        runner,
        ['get', 'error_code', '1', '--fields', 'id,name'],
        httpx.MockTransport(handler),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {'id': 1, 'name': 'test_error'}


def test_list_resource(
    runner: CliRunner,
    list_ref_response: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith('/error_code/')
        assert request.url.params['offset'] == '0'
        assert request.url.params['limit'] == '20'
        assert request.url.params['expand'] == 'true'
        return httpx.Response(200, json=list_ref_response)

    result = _invoke(
        runner,
        ['list', 'error_code', '--limit', '20'],
        httpx.MockTransport(handler),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['count'] == 1234
    assert payload['offset'] == 0
    assert payload['limit'] == 20
    assert len(payload['results']) == 1
    assert payload['next'] == {'offset': 20, 'limit': 20, 'expand': True}


def test_get_by_name(
    runner: CliRunner,
    error_code_item: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith('/error_code/test_error')
        return httpx.Response(
            200,
            json={'data': {'1': error_code_item}},
        )

    result = _invoke(
        runner,
        ['get-by-name', 'error_code', 'test_error'],
        httpx.MockTransport(handler),
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['1']['name'] == 'test_error'


def test_get_by_name_non_named_resource(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['get-by-name', 'peak_pool', 'foo'])
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload['error'] == 'resource does not support name lookup'


def test_pretty_output(
    runner: CliRunner,
    error_code_item: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=error_code_item)

    ctx = CliContext(transport=httpx.MockTransport(handler), pretty=True)
    result = runner.invoke(cli_main, ['get', 'error_code', '1'], obj=ctx)
    assert result.exit_code == 0
    assert '\n' in result.output
    assert '  "id": 1' in result.output


def test_skill_info(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['skill'])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['name'] == 'seerapi-cli'
    assert '--target' in payload['install']
    assert payload['source_path'].endswith('seerapi-cli')


def test_skill_path(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['skill', 'path'])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['path'].endswith('seerapi-cli')


def test_skill_install_requires_target(runner: CliRunner) -> None:
    result = runner.invoke(cli_main, ['skill', 'install'], env={})
    assert result.exit_code != 0


def test_skill_install(runner: CliRunner, tmp_path) -> None:
    target = tmp_path / 'agent-skills'
    result = runner.invoke(
        cli_main,
        ['skill', 'install', '--target', str(target)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['installed'] is True
    assert (target / 'seerapi-cli' / 'SKILL.md').is_file()
    assert (target / 'seerapi-cli' / 'examples.md').is_file()


def test_skill_install_to_final_dir(runner: CliRunner, tmp_path) -> None:
    target = tmp_path / 'agent-skills' / 'seerapi-cli'
    result = runner.invoke(
        cli_main,
        ['skill', 'install', '--target', str(target)],
    )
    assert result.exit_code == 0
    assert (target / 'SKILL.md').is_file()
