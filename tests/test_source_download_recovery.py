from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import check_api_data_publication as guard
from scripts import release_api_data_source as source


@pytest.mark.parametrize('status', [408, 429, 503])
def test_retryable_status_has_exactly_three_requests(tmp_path, monkeypatch, status):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 22, str(status), 'unavailable')

    monkeypatch.setattr(source.subprocess, 'run', run)
    monkeypatch.setattr(source.time, 'sleep', lambda _: None)
    target = tmp_path / 'config.json'
    target.write_bytes(b'old')
    with pytest.raises(RuntimeError, match='Source download failed'):
        source.download_with_retries(
            'https://api.github.com/config',
            target,
            accept='application/vnd.github.raw+json',
            stage='config_partner',
        )
    assert len(calls) == 3
    assert target.read_bytes() == b'old'
    assert not target.with_name('config.json.part').exists()


@pytest.mark.parametrize('code', [18, 28, 56])
def test_stream_and_connect_failures_can_succeed_on_third_attempt(
    tmp_path, monkeypatch, code
):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        target = Path(command[command.index('--output') + 1])
        target.write_bytes(b'complete' if len(calls) == 3 else b'partial')
        assert kwargs['timeout'] == 65
        assert command[command.index('--retry') + 1] == '0'
        assert command[command.index('--connect-timeout') + 1] == '15'
        assert command[command.index('--max-time') + 1] == '60'
        return subprocess.CompletedProcess(
            command,
            0 if len(calls) == 3 else code,
            '200' if len(calls) == 3 else '000',
            'interrupted',
        )

    monkeypatch.setattr(source.subprocess, 'run', run)
    monkeypatch.setattr(source.time, 'sleep', lambda _: None)
    target = tmp_path / 'file'
    source.download_with_retries('https://api.github.com/config', target, accept='*/*')
    assert len(calls) == 3
    assert target.read_bytes() == b'complete'


def test_process_deadline_and_cancellation_do_not_leak_partial(tmp_path, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        Path(command[command.index('--output') + 1]).write_bytes(b'partial')
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])

    monkeypatch.setattr(source.subprocess, 'run', run)
    monkeypatch.setattr(source.time, 'sleep', lambda _: None)
    target = tmp_path / 'file'
    with pytest.raises(RuntimeError, match='deadline'):
        source.download_with_retries(
            'https://api.github.com/config', target, accept='*/*'
        )
    assert len(calls) == 3
    assert not target.with_name('file.part').exists()
    calls.clear()

    def cancel(command, **kwargs):
        calls.append(command)
        Path(command[command.index('--output') + 1]).write_bytes(b'partial')
        raise KeyboardInterrupt

    monkeypatch.setattr(source.subprocess, 'run', cancel)
    with pytest.raises(KeyboardInterrupt):
        source.download_with_retries(
            'https://api.github.com/config', target, accept='*/*'
        )
    assert len(calls) == 1
    assert not target.with_name('file.part').exists()


def test_logs_identify_stage_without_secrets(tmp_path, monkeypatch, capsys):
    url = 'https://user:password@api.github.com/config?token=query-secret'

    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 22, '403', f'{url} Bearer auth-secret X-Key: header-secret'
        )

    monkeypatch.setattr(source.subprocess, 'run', run)
    with pytest.raises(RuntimeError) as error:
        source.download_with_retries(
            url,
            tmp_path / 'file',
            accept='*/*',
            token='auth-secret',
            extra_headers=['X-Key: header-secret'],
            stage='config_partner',
        )
    log = capsys.readouterr().err + str(error.value)
    assert 'stage=config_partner' in log
    assert 'elapsed=' in log
    assert 'HTTP 403' in log
    assert 'https://api.github.com/config' in log
    assert 'api-data source unavailable' not in log
    for secret in ('password', 'query-secret', 'auth-secret', 'header-secret'):
        assert secret not in log


def test_resolve_freezes_validated_release_metadata(tmp_path, monkeypatch):
    document = release_document()
    raw = json.dumps(document).encode()
    calls = []

    def download(url, target, **kwargs):
        calls.append((url, kwargs))
        target.write_bytes(raw)

    monkeypatch.setattr(source, 'download_with_retries', download)
    snapshot = tmp_path / 'release.json'
    assert source.resolve_release(metadata_output=snapshot) == (42, 'a' * 64)
    assert snapshot.read_bytes() == raw
    assert len(calls) == 1
    assert calls[0][1]['stage'] == 'api_data_release'


def release_document():
    body = ('a' * 64 + '  seerapi-data.sqlite\n').encode()
    return {
        'assets': [
            {
                'id': 42,
                'name': 'seerapi-data.sqlite',
                'state': 'uploaded',
                'digest': 'sha256:' + 'a' * 64,
            },
            {
                'id': 43,
                'name': 'seerapi-data.sqlite.sha256',
                'state': 'uploaded',
                'digest': 'sha256:' + hashlib.sha256(body).hexdigest(),
            },
        ]
    }


def test_large_configuration_keeps_original_bytes_and_pinned_commit(
    tmp_path, monkeypatch
):
    commit = 'b' * 40
    raw = json.dumps({'large': 'x' * 2_900_000}).encode() + b'\n'
    calls = []

    def download(url, target, **kwargs):
        calls.append((url, kwargs))
        target.write_bytes(raw)

    monkeypatch.setattr(guard, 'download_with_retries', download)
    guard.download_config_files(commit, tmp_path)
    assert len(calls) == 3
    for filename, (url, kwargs) in zip(guard.CONFIG_FILES, calls):
        assert (tmp_path / filename).read_bytes() == raw
        assert (
            url
            == guard.API_BASE + f'config-sources/contents/unity/{filename}?ref={commit}'
        )
        assert kwargs['accept'] == 'application/vnd.github.raw+json'
        assert kwargs['max_time'] == 60


@pytest.mark.parametrize('failure', ['network', 'json'])
def test_configuration_failure_never_publishes_partial_set(
    tmp_path, monkeypatch, failure
):
    output = tmp_path / 'output'
    output.mkdir()
    for filename in guard.CONFIG_FILES:
        (output / filename).write_bytes(b'previous')
    calls = []

    def download(url, target, **kwargs):
        calls.append(url)
        if len(calls) == 2:
            if failure == 'network':
                raise RuntimeError('download exhausted')
            target.write_bytes(b'not JSON')
        else:
            target.write_bytes(b'{}')

    monkeypatch.setattr(guard, 'download_with_retries', download)
    with pytest.raises((RuntimeError, ValueError)):
        guard.download_config_files('b' * 40, output)
    assert len(calls) == 2
    for filename in guard.CONFIG_FILES:
        assert (output / filename).read_bytes() == b'previous'


@pytest.mark.parametrize('change', ['id', 'digest', 'checksum'])
def test_release_pin_or_checksum_mismatch_fails(tmp_path, monkeypatch, change):
    document = release_document()
    if change == 'id':
        document['assets'][0]['id'] = 44
    elif change == 'digest':
        document['assets'][0]['digest'] = 'sha256:' + 'b' * 64

    def download(url, target, **kwargs):
        assert url == source.ASSET_URL + '43'
        assert kwargs['stage'] == 'api_data_checksum'
        assert kwargs['max_time'] == 60
        assert kwargs['expected_sha256'] == document['assets'][1][
            'digest'
        ].removeprefix('sha256:')
        target.write_text('b' * 64 + '  seerapi-data.sqlite\n')

    monkeypatch.setattr(guard, 'download_with_retries', download)
    with pytest.raises(ValueError, match='differs'):
        guard.release_checksum(document, 42, 'a' * 64)


def test_guard_uses_frozen_metadata_and_does_not_fetch_moving_latest(
    tmp_path, monkeypatch
):
    commit = 'b' * 40
    metadata = tmp_path / 'release.json'
    metadata.write_text(json.dumps(release_document()))
    documents = {
        'config-sources/commits/main': {'sha': commit},
        'api-data/contents/.build-state/publication.json?ref=pipeline-state': {
            'content': base64.b64encode(
                json.dumps({'config': commit, 'sha256': 'a' * 64}).encode()
            ).decode(),
        },
        f'config-sources/contents/unity/.version?ref={commit}': {
            'content': base64.b64encode(b'20261127104733').decode(),
        },
    }
    monkeypatch.setattr(guard, 'get_json', documents.__getitem__)
    monkeypatch.setattr(guard, 'release_checksum', lambda *args: 'a' * 64)
    calls = []
    monkeypatch.setattr(
        guard, 'download_config_files', lambda *args: calls.append(args)
    )
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'guard',
            '--release-metadata',
            str(metadata),
            '--asset-id',
            '42',
            '--sha256',
            'a' * 64,
            '--official-version',
            '20261127104733',
            '--config-output-dir',
            str(tmp_path / 'config'),
        ],
    )
    guard.main()
    assert calls == [(commit, tmp_path / 'config')]
    assert f'config_source={commit}' in output.read_text()
    assert 'blocked=false' in output.read_text()


@pytest.mark.parametrize('body', [b'invalid', b'[]'])
def test_damaged_metadata_fails_without_retrying_parse(tmp_path, monkeypatch, body):
    calls = []

    def download(url, target, **kwargs):
        calls.append(url)
        target.write_bytes(body)

    monkeypatch.setattr(guard, 'download_with_retries', download)
    with pytest.raises(ValueError, match=r'Expecting value|Expected a JSON object'):
        guard.get_json('config-sources/commits/main')
    assert len(calls) == 1


def test_workflow_verifies_provenance_before_fingerprints():
    workflow = (
        Path(__file__).parents[1] / '.github/workflows/build-seerapi-data-db.yml'
    ).read_text('utf-8')
    assert 'PARTNER_CONTRACTS_URL:' not in workflow
    assert (
        '--release-metadata .cache/official-packages/api-data-release.json' in workflow
    )
    assert '--asset-id "${api_data_asset_id}" --sha256 "${remote_sha}"' in workflow
    assert workflow.index(
        'python scripts/check_api_data_publication.py'
    ) < workflow.index('remote_partner_sha="$(')
    assert workflow.index("if grep -q '^blocked=true$'") < workflow.index(
        'remote_partner_sha="$('
    )
