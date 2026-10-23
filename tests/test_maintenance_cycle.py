from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import sys

import pytest

from scripts import maintenance_cycle
from scripts.maintenance_baseline import verified_timestamp
from scripts.maintenance_cycle import fingerprint, select_cycle


def _completed_notice():
    return {
        'id': 'weekly-update',
        'type': 2,
        'main_title': '10月23日维护',
        'page_title': '10月23日停服维护更新内容',
        'start': datetime.fromisoformat('2026-10-23T11:07:40+08:00').timestamp(),
        'end': datetime.fromisoformat('2026-10-30T00:00:00+08:00').timestamp(),
        'text': '<n>《赛尔号巅峰之战》于10月23日进行了每周例行更新维护</n>',
    }


def test_completed_update_announcement_advances_stale_maintenance_cycle():
    old = select_cycle(
        [{'type': 3, 'id': 'old', 'start': 1791511200, 'end': 1791529200}],
        {},
        datetime.fromisoformat('2026-10-09T16:00:00+08:00'),
    )
    now = datetime.fromisoformat('2026-10-23T16:00:00+08:00')
    state = select_cycle([_completed_notice()], old, now)
    assert state['current']['start'] == '2026-10-23T11:07:40+08:00'
    assert state['current']['end'] == ''
    assert state['current']['start_basis'] == 'completed_update_announcement'
    assert select_cycle([], state, now) == state


@pytest.mark.parametrize(
    'change',
    [
        {'text': '将于10月23日进行每周例行更新维护'},
        {'text': '于10月16日进行了每周例行更新维护'},
        {'page_title': '10月16日停服维护更新内容'},
        {'type': 4},
        {'text': '于2025年10月23日进行了每周例行更新维护'},
    ],
)
def test_unconfirmed_or_mismatched_announcements_do_not_start_a_cycle(change):
    state = select_cycle(
        [dict(_completed_notice(), **change)],
        {},
        datetime.fromisoformat('2026-10-23T16:00:00+08:00'),
    )
    assert state['current'] is None


def test_future_announcement_is_not_active_before_publication():
    state = select_cycle(
        [_completed_notice()], {}, datetime.fromisoformat('2026-10-23T09:00:00+08:00')
    )
    assert state['current'] is None


def test_precise_maintenance_notice_has_priority_over_same_day_announcement():
    now = datetime.fromisoformat('2026-10-23T16:00:00+08:00')
    announcement = select_cycle([_completed_notice()], {}, now)
    state = select_cycle(
        [
            {
                'id': 'outage',
                'type': 3,
                'start': datetime.fromisoformat(
                    '2026-10-23T10:00:00+08:00'
                ).timestamp(),
                'end': datetime.fromisoformat('2026-10-23T15:00:00+08:00').timestamp(),
            },
            _completed_notice(),
        ],
        announcement,
        now,
    )
    assert state['current']['notice_id'] == 'outage'
    assert list(state['notices']) == ['2026-10-23T10:00:00+08:00']


def test_empty_response_preserves_started_batch_and_future_is_not_activated():
    now = datetime(2026, 10, 9, 2, tzinfo=timezone.utc)
    notices = [
        {
            'type': 3,
            'id': 'current',
            'start': now.timestamp(),
            'end': now.timestamp() + 3600,
        },
        {
            'type': 3,
            'id': 'future',
            'start': now.timestamp() + 86400,
            'end': now.timestamp() + 90000,
        },
    ]
    state = select_cycle(notices, {}, now)
    assert state['current']['start'] == '2026-10-09T10:00:00+08:00'
    assert select_cycle([], state, now) == state
    after_end = datetime(2026, 10, 9, 20, tzinfo=timezone.utc)
    assert select_cycle([], state, after_end)['current'] == state['current']
    next_day = datetime(2026, 10, 10, 2, tzinfo=timezone.utc)
    assert select_cycle([], state, next_day)['current']['notice_id'] == 'future'
    assert fingerprint(select_cycle([], state, now)) == fingerprint(state)


@pytest.mark.parametrize('value', [{}, None, [{'type': 3, 'start': True, 'end': 5}]])
def test_invalid_notice_is_not_an_empty_success(value):
    with pytest.raises(ValueError, match='maintenance'):
        select_cycle(value, {}, datetime.now(timezone.utc))


def test_missing_confirmed_batch_stops_publication(tmp_path, monkeypatch):
    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'[]'

    monkeypatch.setattr(
        maintenance_cycle, 'urlopen', lambda *args, **kwargs: EmptyResponse()
    )
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'maintenance_cycle',
            '--state',
            str(tmp_path / 'state.json'),
            '--output',
            str(tmp_path / 'result.json'),
        ],
    )
    with pytest.raises(SystemExit) as error:
        maintenance_cycle.main()
    assert error.value.code == 2


def test_baseline_requires_checksum_and_aware_generated_time(tmp_path: Path):
    path = tmp_path / 'snapshot.sqlite'
    checksum = tmp_path / 'snapshot.sha256'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE new_content_release(id INTEGER, generated_at TEXT)')
        conn.execute(
            "INSERT INTO new_content_release VALUES (1,'2026-10-08T22:00:00+08:00')"
        )
        conn.execute('CREATE TABLE new_content_source_snapshot(id INTEGER)')
        conn.execute('INSERT INTO new_content_source_snapshot VALUES (1)')
    checksum.write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    start = '2026-10-09T10:00:00+08:00'
    assert verified_timestamp(path, checksum, start) == datetime.fromisoformat(
        '2026-10-08T22:00:00+08:00'
    )
    assert verified_timestamp(path, checksum, '2026-10-08T10:00:00+08:00') is None
    checksum.write_text('0' * 64)
    with pytest.raises(ValueError, match='checksum mismatch'):
        verified_timestamp(path, checksum, start)
