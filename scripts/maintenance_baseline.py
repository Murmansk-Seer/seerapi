"""Pin the newest checksum-verified snapshot generated before maintenance."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess


def verified_timestamp(path: Path, checksum: Path, start: str) -> datetime | None:
    expected = checksum.read_text().split()[0]
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('invalid baseline checksum')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('baseline checksum mismatch')
    boundary = datetime.fromisoformat(start)
    if boundary.tzinfo is None:
        raise ValueError('maintenance start requires a timezone')
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True) as conn:
        if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('invalid baseline database')
        row = conn.execute('SELECT generated_at FROM new_content_release WHERE id=1').fetchone()
        if not row or not conn.execute('SELECT 1 FROM new_content_source_snapshot LIMIT 1').fetchone():
            raise ValueError('baseline has no reliable semantic snapshot')
        stamp = datetime.fromisoformat(str(row[0]))
        if stamp.tzinfo is None:
            raise ValueError('baseline generation timestamp requires a timezone')
        return stamp if stamp < boundary else None


def gh(*args: str) -> str:
    return subprocess.check_output(['gh', *args], text=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--no-publish', action='store_true')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tag = 'seerapi-maintenance-baselines'
    repo = args.repository
    asset = f"maintenance-{int(datetime.fromisoformat(args.start).timestamp())}.sqlite"
    download = ['--repo', repo, '--dir', str(args.output.parent), '--clobber']
    try:
        gh('release', 'view', tag, '--repo', repo)
    except subprocess.CalledProcessError:
        if not args.no_publish:
            gh('release', 'create', tag, '--repo', repo, '--title', 'Maintenance baselines', '--latest=false')
    pinned = args.output.parent / asset
    try:
        gh('release', 'download', tag, '--pattern', asset, '--pattern', asset + '.sha256', *download)
    except subprocess.CalledProcessError:
        pass
    if pinned.exists():
        if verified_timestamp(pinned, Path(str(pinned) + '.sha256'), args.start) is None:
            raise ValueError('pinned baseline is not before maintenance')
        if pinned != args.output:
            shutil.copyfile(pinned, args.output)
        return
    assets = json.loads(gh('release', 'view', 'seerapi-data-history', '--repo', repo, '--json', 'assets'))['assets']
    candidates = []
    for item in assets:
        name = item['name']
        if not re.fullmatch(r'seerapi-data-\d{14}\.sqlite', name):
            continue
        gh('release', 'download', 'seerapi-data-history', '--pattern', name, '--pattern', name + '.sha256', *download)
        path = args.output.parent / name
        stamp = verified_timestamp(path, Path(str(path) + '.sha256'), args.start)
        if stamp is not None:
            candidates.append((stamp, path))
    if not candidates:
        raise ValueError('no trustworthy published pre-maintenance baseline')
    stamp, selected = max(candidates, key=lambda value: value[0])
    shutil.copyfile(selected, pinned)
    checksum = Path(str(pinned) + '.sha256')
    checksum.write_text(f'{hashlib.sha256(pinned.read_bytes()).hexdigest()}  {asset}\n')
    if not args.no_publish:
        gh('release', 'upload', tag, str(pinned), str(checksum), '--repo', repo)
    if pinned != args.output:
        shutil.copyfile(pinned, args.output)
    print(f'Pinned maintenance baseline: {selected.name} generated_at={stamp.isoformat()}')


if __name__ == '__main__':
    main()
