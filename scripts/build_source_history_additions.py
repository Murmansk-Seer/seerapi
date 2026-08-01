#!/usr/bin/env python3
"""Export numeric content entities added between two api-data Git revisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Final

SOURCE_DIRECTORIES: Final = {
    'achievement': 'achievement',
    'pet': 'pet',
    'pet_skin': 'pet_skin',
    'skill': 'skill',
    'mintmark': 'mintmark',
    'suit': 'suit',
    'equip': 'equip',
}


def _added_entities(repository: Path, base: str, head: str) -> list[dict[str, int | str]]:
    paths = [f'data/v1/data/{directory}' for directory in SOURCE_DIRECTORIES]
    result = subprocess.run(
        ['git', 'diff', '--name-status', '--diff-filter=A', base, head, '--', *paths],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    additions: set[tuple[str, int]] = set()
    for line in result.stdout.splitlines():
        status, separator, raw_path = line.partition('\t')
        if status != 'A' or not separator:
            continue
        path = PurePosixPath(raw_path)
        parts = path.parts
        if len(parts) != 6 or parts[:3] != ('data', 'v1', 'data'):
            continue
        directory, entity_id, filename = parts[3:]
        category = SOURCE_DIRECTORIES.get(directory)
        if category is None or filename != 'index.json' or not entity_id.isdecimal():
            continue
        additions.add((category, int(entity_id)))
    return [
        {'category': category, 'entity_id': entity_id}
        for category, entity_id in sorted(additions)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    additions = _added_entities(args.repository, args.base, args.head)
    document = {
        'base_commit': args.base,
        'head_commit': args.head,
        'additions': additions,
    }
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    print(f'source-history additions: {len(additions)}')  # noqa: T201


if __name__ == '__main__':
    main()
