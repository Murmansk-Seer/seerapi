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
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo('Asia/Shanghai')


def baseline_boundary(start: str) -> datetime:
    stamp = datetime.fromisoformat(start)
    if stamp.tzinfo is None:
        raise ValueError('maintenance start requires a timezone')
    return stamp.astimezone(LOCAL_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def verified_timestamp(path: Path, checksum: Path, start: str) -> datetime | None:
    parts = checksum.read_text().split()
    expected = parts[0] if parts else ''
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('invalid baseline checksum')
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('baseline checksum mismatch')
    boundary = baseline_boundary(start)
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True) as conn:
        if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('invalid baseline database')
        row = conn.execute(
            'SELECT generated_at FROM new_content_release WHERE id=1'
        ).fetchone()
        if (
            not row
            or not conn.execute(
                'SELECT 1 FROM new_content_source_snapshot LIMIT 1'
            ).fetchone()
        ):
            raise ValueError('baseline has no reliable semantic snapshot')
        stamp = datetime.fromisoformat(str(row[0]))
        if stamp.tzinfo is None:
            raise ValueError('baseline generation timestamp requires a timezone')
        has_metadata = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='seerapi_metadata'"
        ).fetchone()
        if has_metadata:
            metadata = dict(conn.execute('SELECT key, value FROM seerapi_metadata'))
            if metadata.get('update_cycle_status') in {
                'cycle_unavailable',
                'baseline_unavailable',
                'scheduled',
                'syncing',
            }:
                return None
        return stamp if stamp < boundary else None


def gh(*args: str) -> str:
    return subprocess.check_output(['gh', *args], text=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--no-publish', action='store_true')
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tag = 'seerapi-maintenance-baselines'
    repo = args.repository
    boundary = baseline_boundary(args.start)
    cycle_id = boundary.date().isoformat()
    asset = f'maintenance-{cycle_id}.sqlite'
    binding_name = f'maintenance-{cycle_id}.json'
    download = ['--repo', repo, '--dir', str(args.output.parent), '--clobber']
    try:
        pinned_assets = json.loads(
            gh('release', 'view', tag, '--repo', repo, '--json', 'assets')
        )['assets']
    except subprocess.CalledProcessError:
        pinned_assets = []
        if not args.no_publish:
            gh(
                'release',
                'create',
                tag,
                '--repo',
                repo,
                '--title',
                'Maintenance baselines',
                '--latest=false',
            )
    names = {item['name'] for item in pinned_assets}
    binding_path = args.output.parent / binding_name
    binding = None
    if binding_name in names:
        gh('release', 'download', tag, '--pattern', binding_name, *download)
        binding = json.loads(binding_path.read_text())
        if (
            binding['update_cycle_id'] != cycle_id
            or binding['cutoff'] != boundary.isoformat()
        ):
            raise ValueError('pinned baseline binding has a different cycle')
        asset = binding['asset']
        if not re.fullmatch(r'maintenance-(?:\d+|\d{4}-\d{2}-\d{2})\.sqlite', asset):
            raise ValueError('invalid bound baseline asset')
    elif asset not in names:
        # Migrate existing timestamp pins without modifying their release assets.
        legacy = [
            name
            for name in names
            if re.fullmatch(r'maintenance-\d+\.sqlite', name)
            and datetime.fromtimestamp(int(name[12:-7]), LOCAL_TZ).date()
            == boundary.date()
        ]
        if len(legacy) > 1:
            raise ValueError('ambiguous legacy baseline pins')
        if legacy:
            asset = legacy[0]
    pinned = args.output.parent / asset
    if binding is not None or asset in names:
        gh(
            'release',
            'download',
            tag,
            '--pattern',
            asset,
            '--pattern',
            asset + '.sha256',
            *download,
        )
        stamp = verified_timestamp(pinned, Path(str(pinned) + '.sha256'), args.start)
        if stamp is None:
            raise ValueError(
                'pinned baseline is not before update date or is unconfirmed'
            )
        digest = hashlib.sha256(pinned.read_bytes()).hexdigest()
        if binding is not None and binding['sha256'] != digest:
            raise ValueError('pinned baseline binding checksum mismatch')
        selected = pinned
    else:
        selected, stamp = select_history_baseline(args, download)
        if selected is None or stamp is None:
            args.output.unlink(missing_ok=True)
            if args.github_output:
                with args.github_output.open('a') as stream:
                    stream.write('baseline_available=false\n')
            return
        shutil.copyfile(selected, pinned)
        digest = hashlib.sha256(pinned.read_bytes()).hexdigest()
        checksum = Path(str(pinned) + '.sha256')
        checksum.write_text(f'{digest}  {asset}\n')
        if not args.no_publish:
            gh('release', 'upload', tag, str(pinned), str(checksum), '--repo', repo)
    if binding is None:
        binding_path.write_text(
            json.dumps(
                {
                    'update_cycle_id': cycle_id,
                    'cutoff': boundary.isoformat(),
                    'asset': asset,
                    'sha256': digest,
                    'generated_at': stamp.isoformat(),
                },
                sort_keys=True,
            )
        )
        if not args.no_publish:
            gh('release', 'upload', tag, str(binding_path), '--repo', repo)
    if pinned != args.output:
        shutil.copyfile(pinned, args.output)
    if args.github_output:
        with args.github_output.open('a') as stream:
            stream.write(f'baseline_available=true\nbaseline_sha256={digest}\n')
    print(  # noqa: T201 - CLI publication diagnostic
        f'Pinned maintenance baseline: {selected.name} generated_at={stamp.isoformat()}'
    )


def select_history_baseline(
    args: argparse.Namespace, download: list[str]
) -> tuple[Path | None, datetime | None]:
    repo = args.repository
    assets = json.loads(
        gh(
            'release',
            'view',
            'seerapi-data-history',
            '--repo',
            repo,
            '--json',
            'assets',
        )
    )['assets']
    candidates = []
    for item in assets:
        name = item['name']
        if not re.fullmatch(r'seerapi-data-\d{14}\.sqlite', name):
            continue
        gh(
            'release',
            'download',
            'seerapi-data-history',
            '--pattern',
            name,
            '--pattern',
            name + '.sha256',
            *download,
        )
        path = args.output.parent / name
        stamp = verified_timestamp(path, Path(str(path) + '.sha256'), args.start)
        if stamp is not None:
            candidates.append((stamp, path))
    if not candidates:
        return None, None
    stamp, selected = max(candidates, key=lambda value: value[0])
    return selected, stamp


if __name__ == '__main__':
    main()
