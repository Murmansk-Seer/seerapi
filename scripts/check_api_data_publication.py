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


def publication_matches(state: dict, source: str, digest: str) -> bool:
    return bool(source and digest and state.get('config') == source and state.get('sha256') == digest)


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
    blocked = not publication_matches(state, source, digest)
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        output.write(f'blocked={str(blocked).lower()}\nconfig_source={source}\npublished_source={state.get("config", "")}\n')
    if blocked:
        print('::warning::Current config-sources has no matching verified api-data publication; downstream build blocked, existing Release preserved.')


if __name__ == '__main__':
    main()
