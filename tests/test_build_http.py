from __future__ import annotations

import logging
from pathlib import Path
import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1] / "scripts"
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
        "https://example.test/data",
        method="GET",
        headers={"Range": "bytes=0-15"},
    )

    assert request.get_header("User-agent") == "IronsBot data builder"
    assert request.get_header("Range") == "bytes=0-15"


def test_fetch_package_manifest_uses_versioned_official_path(monkeypatch) -> None:
    client = _client()
    calls: list[str] = []

    def download_bytes(url: str) -> bytes:
        calls.append(url)
        if url.startswith("https://game.test/PackageManifest_Default.version?"):
            return b"20260815120000"
        if url == "https://game.test/PackageManifest_Default_20260815120000.bytes":
            return b"manifest"
        raise AssertionError(url)

    monkeypatch.setattr(client, "download_bytes", download_bytes)
    version, manifest = client.fetch_package_manifest(
        "https://game.test",
        "Default",
        parse_manifest=lambda payload: {"payload": payload},
    )

    assert version == "20260815120000"
    assert manifest == {"payload": b"manifest"}
    assert calls[1] == "https://game.test/PackageManifest_Default_20260815120000.bytes"
