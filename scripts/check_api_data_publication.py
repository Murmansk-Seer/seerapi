"""Block mixed-generation builds until api-data publishes the current source."""

from __future__ import annotations

import base64
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

try:
    from .release_api_data_source import (
        ASSET_URL,
        DownloadNotFoundError,
        download_with_retries,
        parse_release_asset,
    )
except ImportError:
    from release_api_data_source import (
        ASSET_URL,
        DownloadNotFoundError,
        download_with_retries,
        parse_release_asset,
    )

API_BASE = 'https://api.github.com/repos/Murmansk-Seer/'
CONFIG_FILES = (
    'partner_contracts.json',
    'itemsOptimizeCatItems17.json',
    'signIconFight.json',
)


def get_json(path: str):
    with tempfile.TemporaryDirectory(prefix='publication-json-') as directory:
        target = Path(directory) / 'response.json'
        try:
            download_with_retries(
                API_BASE + path,
                target,
                accept='application/vnd.github+json',
                token=os.environ.get('GH_TOKEN', ''),
                max_time=60,
                stage='publication_metadata',
            )
        except DownloadNotFoundError:
            return None
        result = json.loads(target.read_text('utf-8'))
    if not isinstance(result, dict):
        raise ValueError(f'Expected a JSON object from GitHub API: {path}')
    return result


def publication_matches(
    state: dict,
    source: str,
    digest: str,
    *,
    source_tree: str = '',
    published_tree: str = '',
) -> bool:
    # A history-only merge changes the commit but not its complete Git tree.
    # Never infer equality from an empty/truncated compare API file listing.
    same_source = state.get('config') == source or bool(
        source_tree and published_tree and source_tree == published_tree
    )
    return bool(
        source
        and state.get('config')
        and digest
        and same_source
        and state.get('sha256') == digest
    )


def verified_publication_matches(state: dict, source_info: dict, digest: str) -> bool:
    source = source_info['sha']
    if publication_matches(state, source, digest):
        return True
    if not state.get('config') or not digest or state.get('sha256') != digest:
        return False
    # Resolve both immutable commits, not moving main or the upstream repository.
    published = get_json(f'config-sources/commits/{state["config"]}')
    if published is None or published.get('sha') != state['config']:
        return False
    return publication_matches(
        state,
        source,
        digest,
        source_tree=source_info.get('commit', {}).get('tree', {}).get('sha', ''),
        published_tree=published.get('commit', {}).get('tree', {}).get('sha', ''),
    )


def release_checksum(document: dict, asset_id: int, expected_sha256: str) -> str:
    if parse_release_asset(document) != (asset_id, expected_sha256):
        raise ValueError(
            'Pinned api-data asset ID/SHA256 differs from Release metadata'
        )
    checksums = [
        asset
        for asset in document['assets']
        if isinstance(asset, dict)
        and asset.get('name') == 'seerapi-data.sqlite.sha256'
        and asset.get('state') == 'uploaded'
    ]
    if len(checksums) != 1:
        raise ValueError('Release must contain exactly one uploaded database checksum')
    asset = checksums[0]
    if type(asset.get('id')) is not int or asset['id'] <= 0:
        raise ValueError('Invalid checksum asset ID')
    checksum_digest = asset.get('digest', '')
    if not isinstance(checksum_digest, str) or not re.fullmatch(
        r'sha256:[0-9a-f]{64}', checksum_digest
    ):
        raise ValueError('Invalid checksum asset SHA256')
    with tempfile.TemporaryDirectory(prefix='publication-checksum-') as directory:
        target = Path(directory) / 'checksum'
        download_with_retries(
            ASSET_URL + str(asset['id']),
            target,
            accept='application/octet-stream',
            expected_sha256=checksum_digest.removeprefix('sha256:'),
            token=os.environ.get('GH_TOKEN', ''),
            max_time=60,
            stage='api_data_checksum',
        )
        text = target.read_text('utf-8').strip()
    match = re.fullmatch(r'([0-9a-f]{64})\s+\*?seerapi-data\.sqlite', text)
    if match is None or match[1] != expected_sha256:
        raise ValueError('Release checksum file differs from pinned database SHA256')
    return match[1]


def download_config_files(source: str, output: Path) -> None:
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('Configuration source must be an immutable Git commit')
    # Raw media works for the >1 MB item catalog, whose default JSON has no content.
    with tempfile.TemporaryDirectory(prefix='publication-config-') as directory:
        candidate = Path(directory)
        for filename in CONFIG_FILES:
            target = candidate / filename
            download_with_retries(
                f'{API_BASE}config-sources/contents/unity/{filename}?ref={quote(source, safe="")}',
                target,
                accept='application/vnd.github.raw+json',
                token=os.environ.get('GH_TOKEN', ''),
                max_time=60,
                stage='config_' + filename.removesuffix('.json').lower(),
            )
            if not isinstance(json.loads(target.read_text('utf-8')), (dict, list)):
                raise ValueError(f'Invalid configuration JSON: {filename}')
        output.mkdir(parents=True, exist_ok=True)
        for filename in CONFIG_FILES:
            (output / filename).write_bytes((candidate / filename).read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-version')
    parser.add_argument('--release-metadata', type=Path)
    parser.add_argument('--asset-id', type=int)
    parser.add_argument('--sha256')
    parser.add_argument('--config-output-dir', type=Path)
    args = parser.parse_args()
    if (args.asset_id is None) != (args.sha256 is None):
        parser.error('--asset-id and --sha256 must be supplied together')
    if args.asset_id is not None and (
        args.asset_id <= 0 or not re.fullmatch(r'[0-9a-f]{64}', args.sha256)
    ):
        parser.error('invalid pinned database asset ID/SHA256')
    # Reuse the exact metadata resolved by plan; standalone callers resolve once.
    checksum = (
        json.loads(args.release_metadata.read_text('utf-8'))
        if args.release_metadata
        else get_json('api-data/releases/tags/latest')
    )
    if checksum is None:
        raise RuntimeError('api-data latest Release is unavailable')
    pinned = parse_release_asset(checksum)
    digest = release_checksum(
        checksum, args.asset_id or pinned[0], args.sha256 or pinned[1]
    )
    source_info = get_json('config-sources/commits/main')
    if source_info is None:
        raise RuntimeError(
            'config-sources main is unavailable; cannot establish publication provenance'
        )
    source = source_info['sha']
    content = get_json(
        'api-data/contents/.build-state/publication.json?ref=pipeline-state'
    )
    state = json.loads(base64.b64decode(content['content'])) if content else {}
    blocked = not verified_publication_matches(state, source_info, digest)
    if args.official_version:
        config_version = get_json(
            f'config-sources/contents/unity/.version?ref={source}'
        )
        published_version = (
            base64.b64decode(config_version['content']).decode().strip()
            if config_version
            else ''
        )
        if (
            not published_version.isdecimal()
            or published_version != args.official_version
        ):
            blocked = True
            print(
                f'::warning::Official ConfigPackage {args.official_version} is not yet represented by config-sources {published_version}; preserving the existing Release.'
            )
    if not blocked and args.config_output_dir:
        download_config_files(source, args.config_output_dir)
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write(
            f'blocked={str(blocked).lower()}\nconfig_source={source}\npublished_source={state.get("config", "")}\n'
        )
    if blocked:
        print(
            '::warning::Current config-sources has no matching verified api-data publication; downstream build blocked, existing Release preserved.'
        )


if __name__ == '__main__':
    main()
