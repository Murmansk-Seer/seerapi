from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import sys

import pytest

from scripts import maintenance_cycle
from scripts.maintenance_baseline import verified_timestamp
from scripts.maintenance_cycle import fingerprint, select_cycle


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
