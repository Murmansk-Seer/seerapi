from __future__ import annotations

import logging
from pathlib import Path
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from build_http import BuildHttpClient, BuildHttpConfig


def _client() -> BuildHttpClient:
    return BuildHttpClient(
        BuildHttpConfig(
            timeout_seconds=10,
            retry_attempts=2,
            retry_backoff_seconds=0,
        ),
        logger=logging.getLogger(__name__),
    )


def test_request_uses_default_user_agent_and_preserves_extra_headers() -> None:
    request = _client().request(
        'https://example.test/data',
        method='GET',
        headers={'Range': 'bytes=0-15'},
    )

    assert request.get_header('User-agent') == 'SeerAPI data builder'
    assert request.get_header('Range') == 'bytes=0-15'


def test_fetch_package_manifest_uses_versioned_official_path(monkeypatch) -> None:
    client = _client()
    calls: list[str] = []

    def download_bytes(url: str) -> bytes:
        calls.append(url)
        if url.startswith('https://game.test/PackageManifest_Default.version?'):
            return b'20260815120000'
        if url == 'https://game.test/PackageManifest_Default_20260815120000.bytes':
            return b'manifest'
        raise AssertionError(url)

    monkeypatch.setattr(client, 'download_bytes', download_bytes)
    version, manifest = client.fetch_package_manifest(
        'https://game.test',
        'Default',
        parse_manifest=lambda payload: {'payload': payload},
    )

    assert version == '20260815120000'
    assert manifest == {'payload': b'manifest'}
    assert calls[1] == 'https://game.test/PackageManifest_Default_20260815120000.bytes'


def test_official_package_cache_reuses_plan_downloads(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / 'ConfigPackage'
    package_dir.mkdir()
    (package_dir / 'PackageManifest_ConfigPackage.version').write_bytes(
        b'20260927120000'
    )
    (package_dir / 'PackageManifest_ConfigPackage_20260927120000.bytes').write_bytes(
        b'manifest'
    )
    (package_dir / '0123456789abcdef0123456789abcdef').write_bytes(b'bundle')
    client = BuildHttpClient(
        BuildHttpConfig(
            timeout_seconds=10,
            retry_attempts=2,
            retry_backoff_seconds=0,
            official_package_cache_dir=tmp_path,
        ),
        logger=logging.getLogger(__name__),
    )
    monkeypatch.setattr(
        'build_http.urlopen',
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('network')),
    )

    version, manifest = client.fetch_package_manifest(
        'https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/',
        'ConfigPackage',
        parse_manifest=lambda payload: payload,
    )

    assert version == '20260927120000'
    assert manifest == b'manifest'
    assert (
        client.download_bytes(
            'https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/'
            '0123456789abcdef0123456789abcdef'
        )
        == b'bundle'
    )
