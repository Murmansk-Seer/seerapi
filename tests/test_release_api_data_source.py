from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import release_api_data_source as source


def _asset(*, digest: str | None = None) -> dict[str, Any]:
    return {
        'assets': [
            {
                'id': 42,
                'name': 'seerapi-data.sqlite',
                'state': 'uploaded',
                'digest': digest or 'sha256:' + 'a' * 64,
            }
        ]
    }


def test_parse_release_asset_pins_uploaded_database() -> None:
    assert source.parse_release_asset(_asset()) == (42, 'a' * 64)


def test_resolve_command_writes_machine_readable_outputs(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    output = tmp_path / 'github-output'
    monkeypatch.setattr(source, 'resolve_release', lambda **_kwargs: (42, 'a' * 64))
    monkeypatch.setattr(
        sys,
        'argv',
        ['release_api_data_source.py', 'resolve', '--github-output', str(output)],
    )

    assert source.main() == 0
    assert capsys.readouterr().out == f'42 {"a" * 64}\n'
    assert output.read_text(encoding='utf-8') == (
        f'api_data_asset_id=42\nremote_sha={"a" * 64}\n'
    )


@pytest.mark.parametrize(
    'change',
    [
        lambda doc: doc['assets'].append(doc['assets'][0].copy()),
        lambda doc: doc['assets'][0].update({'state': 'starter'}),
        lambda doc: doc['assets'][0].update({'digest': None}),
        lambda doc: doc['assets'][0].update({'digest': 'sha256:bad'}),
        lambda doc: doc['assets'][0].update({'id': 0}),
    ],
)
def test_parse_release_asset_rejects_invalid_metadata(change) -> None:
    document = _asset()
    change(document)
    with pytest.raises(ValueError, match='api-data Release'):
        source.parse_release_asset(document)


def test_network_timeout_warns_then_succeeds_on_third_total_attempt(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    attempts: list[list[str]] = []
    sleeps: list[int] = []

    def fake_run(command, **_kwargs):
        attempts.append(command)
        if len(attempts) < 3:
            return subprocess.CompletedProcess(command, 28, '000', 'SSL timeout')
        Path(command[command.index('--output') + 1]).write_bytes(b'payload')
        return subprocess.CompletedProcess(command, 0, '200', '')

    monkeypatch.setattr(source.subprocess, 'run', fake_run)
    monkeypatch.setattr(source.time, 'sleep', sleeps.append)
    output = tmp_path / 'release.json'

    source.download_with_retries(
        'https://api.github.com/example',
        output,
        accept='application/vnd.github+json',
    )

    assert len(attempts) == 3
    assert sleeps == [2, 4]
    assert output.read_bytes() == b'payload'
    assert capsys.readouterr().err.count('::warning') == 2


def test_three_total_failures_warn_and_raise(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    attempts = 0

    def fake_run(command, **_kwargs):
        nonlocal attempts
        attempts += 1
        return subprocess.CompletedProcess(command, 28, '000', 'SSL timeout')

    monkeypatch.setattr(source.subprocess, 'run', fake_run)
    monkeypatch.setattr(source.time, 'sleep', lambda _delay: None)
    output = tmp_path / 'release.json'

    with pytest.raises(RuntimeError, match='api-data source unavailable'):
        source.download_with_retries(
            'https://api.github.com/example',
            output,
            accept='application/vnd.github+json',
        )

    assert attempts == 3
    assert not output.exists()
    assert capsys.readouterr().err.count('::warning') == 3


def test_nonretryable_http_error_fails_immediately(tmp_path: Path, monkeypatch) -> None:
    attempts = 0

    def fake_run(command, **_kwargs):
        nonlocal attempts
        attempts += 1
        return subprocess.CompletedProcess(command, 22, '404', 'Not Found')

    monkeypatch.setattr(source.subprocess, 'run', fake_run)

    with pytest.raises(RuntimeError, match='HTTP 404'):
        source.download_with_retries(
            'https://api.github.com/example',
            tmp_path / 'missing',
            accept='application/vnd.github+json',
        )

    assert attempts == 1


def test_database_hash_mismatch_retries_and_does_not_publish(
    tmp_path: Path, monkeypatch
) -> None:
    attempts = 0

    def fake_run(command, **_kwargs):
        nonlocal attempts
        attempts += 1
        Path(command[command.index('--output') + 1]).write_bytes(b'wrong')
        return subprocess.CompletedProcess(command, 0, '200', '')

    monkeypatch.setattr(source.subprocess, 'run', fake_run)
    monkeypatch.setattr(source.time, 'sleep', lambda _delay: None)
    output = tmp_path / 'api-data.sqlite'

    with pytest.raises(RuntimeError, match='SHA256'):
        source.download_with_retries(
            'https://api.github.com/example',
            output,
            accept='application/octet-stream',
            expected_sha256=hashlib.sha256(b'expected').hexdigest(),
        )

    assert attempts == 3
    assert not output.exists()
    assert not (tmp_path / 'api-data.sqlite.part').exists()
