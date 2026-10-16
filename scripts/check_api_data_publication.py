"""Block mixed-generation builds until api-data publishes the current source."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def get_json(path: str):
    headers = {'Accept': 'application/vnd.github+json'}
    if token := os.environ.get('GH_TOKEN'):
        headers['Authorization'] = f'Bearer {token}'
    for attempt in range(3):
        try:
            with urlopen(Request(f'https://api.github.com/repos/Murmansk-Seer/{path}', headers=headers), timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404:
                return None
            if attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep((attempt + 1) * 2)
    raise AssertionError('unreachable')


def publication_matches(
    state: dict, source: str, digest: str, *, source_tree: str = '', published_tree: str = ''
) -> bool:
    # A history-only merge changes the commit but not its complete Git tree.
    # Never infer equality from an empty/truncated compare API file listing.
    same_source = state.get('config') == source or bool(
        source_tree and published_tree and source_tree == published_tree
    )
    return bool(source and state.get('config') and digest and same_source and state.get('sha256') == digest)


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
        state, source, digest,
        source_tree=source_info.get('commit', {}).get('tree', {}).get('sha', ''),
        published_tree=published.get('commit', {}).get('tree', {}).get('sha', ''),
    )


def main():
    source_info = get_json('config-sources/commits/main')
    if source_info is None:
        raise RuntimeError('config-sources main is unavailable; cannot establish publication provenance')
    source = source_info['sha']
    content = get_json('api-data/contents/.build-state/publication.json?ref=main')
    state = json.loads(base64.b64decode(content['content'])) if content else {}
    checksum = get_json('api-data/releases/tags/latest')
    if checksum is None:
        raise RuntimeError('api-data latest Release is unavailable')
    asset = next(item for item in checksum['assets'] if item['name'] == 'seerapi-data.sqlite.sha256')
    # Public asset URL; no authorization token is forwarded to another host.
    with urlopen(asset['browser_download_url'], timeout=60) as response:
        digest = response.read().decode().split()[0]
    blocked = not verified_publication_matches(state, source_info, digest)
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write(f'blocked={str(blocked).lower()}\nconfig_source={source}\npublished_source={state.get("config", "")}\n')
    if blocked:
        print('::warning::Current config-sources has no matching verified api-data publication; downstream build blocked, existing Release preserved.')


if __name__ == '__main__':
    main()
