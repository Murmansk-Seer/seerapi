"""Resolve and download the immutable api-data release asset for a build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

RELEASE_URL = 'https://api.github.com/repos/Murmansk-Seer/api-data/releases/tags/latest'
ASSET_URL = 'https://api.github.com/repos/Murmansk-Seer/api-data/releases/assets/'
ASSET_NAME = 'seerapi-data.sqlite'
TOTAL_ATTEMPTS = 3
SHA256_PATTERN = re.compile(r'sha256:([0-9a-f]{64})\Z')
RETRYABLE_CURL_CODES = {5, 6, 7, 18, 28, 35, 52, 55, 56, 92}
RETRYABLE_HTTP_CODES = {408, 429, *range(500, 600)}


def parse_release_asset(document: dict[str, Any]) -> tuple[int, str]:
    assets = document.get('assets')
    if not isinstance(assets, list):
        raise ValueError('api-data Release has no asset list')
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and asset.get('name') == ASSET_NAME
        and asset.get('state') == 'uploaded'
    ]
    if len(matches) != 1:
        raise ValueError(f'api-data Release must contain exactly one uploaded {ASSET_NAME}')
    asset = matches[0]
    asset_id = asset.get('id')
    digest = asset.get('digest')
    if isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id <= 0:
        raise ValueError('api-data Release asset ID is invalid')
    if not isinstance(digest, str) or (match := SHA256_PATTERN.fullmatch(digest)) is None:
        raise ValueError('api-data Release asset SHA256 digest is missing or invalid')
    return asset_id, match.group(1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _warning(message: str) -> None:
    safe = message.replace('\n', ' ').replace('\r', ' ').replace('::', ':')[:240]
    print(f'::warning title=api-data source retry::{safe}', file=sys.stderr, flush=True)


def download_with_retries(
    url: str,
    destination: Path,
    *,
    accept: str,
    expected_sha256: str | None = None,
    token: str = '',
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + '.part')
    headers = ['--header', f'Accept: {accept}']
    if token:
        headers.extend(['--header', f'Authorization: Bearer {token}'])
    for attempt in range(1, TOTAL_ATTEMPTS + 1):
        partial.unlink(missing_ok=True)
        command = [
            'curl', '-fsSL', '--connect-timeout', '15', '--max-time',
            '180' if expected_sha256 else '120', '--retry', '0',
            *headers, '--output', str(partial), '--write-out', '%{http_code}', url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        try:
            status = int(result.stdout.strip())
        except ValueError:
            status = 0
        if result.returncode == 0 and status == 200 and partial.is_file():
            if expected_sha256 is None or _sha256(partial) == expected_sha256:
                partial.replace(destination)
                return
            failure = 'downloaded database SHA256 does not match the pinned Release asset'
            retryable = True
        else:
            failure = (
                f'HTTP {status or "unavailable"}, curl exit {result.returncode}: '
                f'{result.stderr.strip()}'
            )
            retryable = (
                result.returncode in RETRYABLE_CURL_CODES
                or status in RETRYABLE_HTTP_CODES
            )
        partial.unlink(missing_ok=True)
        _warning(f'attempt {attempt}/{TOTAL_ATTEMPTS} failed: {failure}')
        if not retryable or attempt == TOTAL_ATTEMPTS:
            raise RuntimeError(f'api-data source unavailable: {failure}')
        time.sleep(2 * attempt)


def resolve_release(*, token: str = '') -> tuple[int, str]:
    with tempfile.TemporaryDirectory(prefix='seerapi-api-data-release-') as directory:
        path = Path(directory) / 'release.json'
        download_with_retries(
            RELEASE_URL,
            path,
            accept='application/vnd.github+json',
            token=token,
        )
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as error:
            raise ValueError('api-data Release API returned invalid JSON') from error
    if not isinstance(document, dict):
        raise ValueError('api-data Release API returned invalid metadata')
    return parse_release_asset(document)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command', required=True)
    resolve = subparsers.add_parser('resolve')
    resolve.add_argument('--github-output', type=Path, required=True)
    download = subparsers.add_parser('download')
    download.add_argument('--asset-id', type=int, required=True)
    download.add_argument('--sha256', required=True)
    download.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'resolve':
            asset_id, sha256 = resolve_release(token=os.environ.get('GH_TOKEN', ''))
            with args.github_output.open('a', encoding='utf-8') as output:
                output.write(f'api_data_asset_id={asset_id}\nremote_sha={sha256}\n')
            print(f'{asset_id} {sha256}')
        else:
            if args.asset_id <= 0 or re.fullmatch(r'[0-9a-f]{64}', args.sha256) is None:
                raise ValueError('invalid pinned api-data asset ID or SHA256')
            download_with_retries(
                f'{ASSET_URL}{args.asset_id}',
                args.output,
                accept='application/octet-stream',
                expected_sha256=args.sha256,
                token=os.environ.get('GH_TOKEN', ''),
            )
            print(f'Verified api-data Release asset {args.asset_id} ({args.sha256})')
    except (OSError, RuntimeError, ValueError) as error:
        print(f'::error title=api-data source::{error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
