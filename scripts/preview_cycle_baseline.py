"""Select and verify a published database predating an official preview window."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3

ASSET = re.compile(r'^seerapi-data-(\d{14})\.sqlite$')


def cycle_start(value: str) -> datetime:
    start = datetime.fromisoformat(value)
    if start.tzinfo is None:
        raise ValueError('preview cycle start must have a timezone')
    return start.astimezone(timezone.utc)


def baseline_asset_name(value: str) -> str:
    return f'baseline-{int(cycle_start(value).timestamp())}.sqlite'


def is_pre_window_snapshot(path: Path, value: str) -> bool:
    if not path.is_file():
        return False
    with sqlite3.connect(path) as conn:
        try:
            row = conn.execute(
                'SELECT generated_at FROM new_content_release WHERE id = 1'
            ).fetchone()
        except sqlite3.DatabaseError:
            return False
        if row is None:
            return False
        timestamp = datetime.fromisoformat(str(row[0]))
        return timestamp.tzinfo is not None and timestamp < cycle_start(value)


def candidate_assets(document: dict, value: str) -> list[str]:
    start = cycle_start(value)
    matches = []
    for asset in document.get('assets', []):
        name = str(asset.get('name', ''))
        matched = ASSET.fullmatch(name)
        if matched is None:
            continue
        version = datetime.strptime(matched[1], '%Y%m%d%H%M%S').replace(
            tzinfo=timezone.utc
        )
        if version < start:
            matches.append((version, name))
    return [name for _, name in sorted(matches, reverse=True)]


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    for name in ('asset-name', 'candidates'):
        command = sub.add_parser(name)
        command.add_argument('start')
        if name == 'candidates':
            command.add_argument('history_json', type=Path)
    check = sub.add_parser('check')
    check.add_argument('start')
    check.add_argument('database', type=Path)
    args = parser.parse_args()
    if args.action == 'asset-name':
        print(baseline_asset_name(args.start))  # noqa: T201 - workflow output
    elif args.action == 'candidates':
        for name in candidate_assets(
            json.loads(args.history_json.read_text(encoding='utf-8')), args.start
        ):
            print(name)  # noqa: T201 - workflow output
    elif not is_pre_window_snapshot(args.database, args.start):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
