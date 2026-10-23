"""Replay verified real snapshots; dates label semantic diffs, not outage times."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile

import build_new_content_index as indexer
from maintenance_baseline import verified_timestamp
from maintenance_cycle import select_cycle


def verified(path: Path) -> None:
    expected = Path(str(path) + '.sha256').read_text().split()[0]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f'snapshot checksum mismatch: {path.name}')
    with closing(
        sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)
    ) as conn:
        if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError(f'invalid snapshot: {path.name}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for label in ('before', 'oct09', 'oct16', 'oct23'):
        parser.add_argument('--' + label, type=Path, required=True)
    args = parser.parse_args()
    paths = [args.before, args.oct09, args.oct16, args.oct23]
    for path in paths:
        verified(path)
    report = {'semantic_differences': [], 'simulations': {}}
    for previous, current, day, expected in zip(
        paths, paths[1:], ('09', '16', '23'), (54, 111, 48), strict=False
    ):
        state = indexer.build_release_state(
            current,
            previous,
            'history-replay',
            cycle_start=f'2026-10-{day}T00:00:00+08:00',
            baseline_path=previous,
        )
        if len(state.items) != expected:
            raise ValueError(f'Oct {day}: {len(state.items)} != {expected}')
        report['semantic_differences'].append(
            {'date': f'2026-10-{day}', 'count': len(state.items)}
        )
    saved = {
        'current': None,
        'notices': {
            'old': {
                'start': '2026-10-09T10:00:00+08:00',
                'end': '',
                'notice_id': 'reused',
            }
        },
    }
    pending = select_cycle(
        [], saved, datetime.fromisoformat('2026-10-16T18:00:00+08:00')
    )
    assert pending['status'] == 'cycle_unavailable'
    mixed = indexer.build_release_state(
        args.oct16,
        args.oct09,
        'reproduce-old',
        cycle_start=saved['notices']['old']['start'],
        baseline_path=args.before,
    )
    assert len(mixed.items) == 160
    with tempfile.TemporaryDirectory() as folder:
        current = Path(folder) / 'current.sqlite'
        shutil.copyfile(args.oct16, current)
        original_clock, original_args = indexer.datetime, sys.argv

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromisoformat('2026-10-16T18:00:00+08:00').astimezone(
                    tz
                )

        try:
            indexer.datetime = Clock
            sys.argv = [
                'index',
                '--current',
                str(current),
                '--current-git-sha',
                'replay',
                '--maintenance-mode',
                '--maintenance-start',
                pending['current']['start'],
                '--baseline',
                str(args.before),
            ]
            indexer.main()
        finally:
            indexer.datetime, sys.argv = original_clock, original_args
        with closing(sqlite3.connect(current)) as conn:
            assert (
                conn.execute('SELECT count(*) FROM new_content_item').fetchone()[0] == 0
            )
            metadata = dict(conn.execute('SELECT key,value FROM seerapi_metadata'))
            assert metadata['update_cycle_status'] == 'cycle_unavailable'
        gc.collect()
    report['simulations']['missing_notice'] = {
        'previous_mixed_count': 160,
        'stale_count': 49,
        'status': pending['status'],
        'visible_count': 0,
    }
    old = {
        'current': {
            'start': '2026-10-23T11:07:40+08:00',
            'end': '',
            'notice_id': 'reused',
        },
        'notices': {},
    }
    edited = {
        'type': 2,
        'id': 'reused',
        'page_title': '10月23日维护',
        'text': '于10月23日进行了每周例行更新维护',
        'start': datetime.fromisoformat('2026-10-23T19:00:00+08:00').timestamp(),
    }
    stable = select_cycle(
        [edited], old, datetime.fromisoformat('2026-10-23T20:00:00+08:00')
    )
    assert stable['current'] == old['current']
    assert (
        verified_timestamp(
            args.oct23, Path(str(args.oct23) + '.sha256'), '2026-10-23T19:00:00+08:00'
        )
        is None
    )
    state = indexer.build_release_state(
        args.oct23,
        args.oct16,
        'edited-notice',
        cycle_start=stable['current']['start'],
        baseline_path=args.oct16,
    )
    assert len(state.items) == 48
    with sqlite3.connect(args.oct23) as conn:
        published = set(conn.execute('SELECT category,entity_id FROM new_content_item'))
    # The original Oct 23 publication counted three skin-only owner updates.
    published -= {('autocard_card', card_id) for card_id in (6, 30, 47)}
    assert {(item.category, item.entity_id) for item in state.items} == published
    report['simulations']['edited_notice'] = {
        'count': 48,
        'current_snapshot_rejected_as_baseline': True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))  # noqa: T201


if __name__ == '__main__':
    main()
