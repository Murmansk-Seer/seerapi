from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from scripts import maintenance_cycle
from scripts.maintenance_cycle import fingerprint, select_cycle
from scripts.official_update_timing import (
    release_summary,
    validate_published_timing,
    validate_timing,
)


def clock(value='2026-11-14T15:00:00+08:00'):
    return datetime.fromisoformat(value)


def completed():
    return {
        'id': '6842696ec36cbdd61c0dc942',
        'type': 2,
        'page_title': '11月13日停服维护更新内容',
        'start': clock('2026-11-13T11:07:40+08:00').timestamp(),
        'end': clock('2026-11-20T00:00:00+08:00').timestamp(),
        'text': '《赛尔号巅峰之战》于11月13日进行了每周例行更新维护',
    }


def planned(start='2026-11-20T10:00:00+08:00', end='2026-11-20T15:00:00+08:00'):
    return {
        'id': 'planned',
        'type': 3,
        'start': clock(start).timestamp(),
        'end': clock(end).timestamp(),
    }


def test_real_completed_announcement_is_not_an_outage_window():
    state = select_cycle([completed()], {}, clock())
    value = state['official_update_timing']
    assert value['next_update'] is None
    last = value['last_update']
    assert last['date'] == '2026-11-13'
    assert last['planned_start'] is last['planned_end'] is None
    assert last['completion_announced_at'] == '2026-11-13T11:07:40+08:00'
    assert last['status'] == 'completed_announced'
    assert last['evidence'][0]['notice_id'] == completed()['id']


def test_next_maintenance_changes_or_withdraws_without_changing_current_anchor():
    state = select_cycle([completed(), planned()], {}, clock())
    assert (
        state['official_update_timing']['next_update']['planned_start']
        == '2026-11-20T10:00:00+08:00'
    )
    moved = select_cycle(
        [
            completed(),
            planned('2026-11-21T10:00:00+08:00', '2026-11-21T12:00:00+08:00'),
        ],
        state,
        clock(),
    )
    assert moved['current'] == state['current']
    assert moved['official_update_timing']['next_update']['date'] == '2026-11-21'
    withdrawn = select_cycle([completed()], moved, clock())
    assert withdrawn['official_update_timing']['next_update'] is None
    later = select_cycle([], withdrawn, clock('2026-11-22T12:00:00+08:00'))
    assert later['official_update_timing']['last_update']['date'] == '2026-11-13'


def test_future_or_unpublished_completion_text_cannot_announce_next_maintenance():
    future = dict(completed(), start=clock('2026-11-13T19:00:00+08:00').timestamp())
    value = select_cycle([future], {}, clock('2026-11-13T09:00:00+08:00'))[
        'official_update_timing'
    ]
    assert value['last_update'] is value['next_update'] is None


def test_same_day_schedule_and_completed_notice_keep_distinct_evidence():
    state = select_cycle(
        [
            planned('2026-11-13T10:00:00+08:00', '2026-11-13T15:00:00+08:00'),
            completed(),
        ],
        {},
        clock(),
    )
    last = state['official_update_timing']['last_update']
    assert last['planned_start'] == '2026-11-13T10:00:00+08:00'
    assert last['planned_end'] == '2026-11-13T15:00:00+08:00'
    assert last['completion_announced_at'] == '2026-11-13T11:07:40+08:00'
    assert len(last['evidence']) == 2
    assert last['status'] == 'completed_announced'
    assert select_cycle([completed()], state, clock())['current'] == state['current']


def test_unchanged_official_data_does_not_rebuild_on_every_check():
    docs = [completed(), planned()]
    first = select_cycle(docs, {}, clock())
    later = select_cycle(docs, first, clock('2026-11-15T15:00:00+08:00'))
    assert first == later
    assert fingerprint(first) == fingerprint(later)


def test_year_boundary_and_unknown_completion_are_not_inferred():
    state = select_cycle(
        [planned('2027-01-01T10:00:00+08:00', '2027-01-01T12:00:00+08:00')],
        {},
        clock('2026-12-31T15:00:00+08:00'),
    )
    assert state['official_update_timing']['next_update']['date'] == '2027-01-01'
    later = select_cycle(
        [planned('2027-01-01T10:00:00+08:00', '2027-01-01T12:00:00+08:00')],
        state,
        clock('2027-01-02T15:00:00+08:00'),
    )
    assert (
        later['official_update_timing']['last_update']['status']
        == 'maintenance_announced'
    )
    assert (
        later['official_update_timing']['last_update']['completion_announced_at']
        is None
    )


@pytest.mark.parametrize('mode', ['network', 'json', 'notice'])
def test_fetch_failure_does_not_write_state_or_success_outputs(
    tmp_path, monkeypatch, mode
):
    saved = tmp_path / 'saved.json'
    saved.write_text('{"previous":"retained"}')
    target, output = tmp_path / 'candidate.json', tmp_path / 'output'
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'maintenance_cycle',
            '--state',
            str(saved),
            '--output',
            str(target),
            '--github-output',
            str(output),
        ],
    )

    def download(url, file, **kwargs):
        assert kwargs['max_time'] == 60
        if mode == 'network':
            raise RuntimeError('all three attempts exhausted')
        file.write_text(
            'broken' if mode == 'json' else '[{"type":3,"start":10,"end":5}]'
        )

    monkeypatch.setattr(maintenance_cycle, 'download_with_retries', download)
    with pytest.raises((ValueError, RuntimeError), match=r'.+'):
        maintenance_cycle.main()
    assert saved.read_text() == '{"previous":"retained"}'
    assert not target.exists()
    assert not output.exists()


def test_published_timing_must_match_frozen_evidence(tmp_path):
    state = select_cycle([completed()], {}, clock())
    frozen = tmp_path / 'maintenance.json'
    frozen.write_text(json.dumps(state))
    with sqlite3.connect(':memory:') as conn:
        conn.execute(
            'CREATE TABLE seerapi_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)'
        )
        conn.execute(
            'INSERT INTO seerapi_metadata VALUES(?,?)',
            ('official_update_timing', json.dumps(state['official_update_timing'])),
        )
        validate_published_timing(conn, frozen)
        bad = dict(
            state['official_update_timing'],
            next_update=state['official_update_timing']['last_update'],
        )
        with pytest.raises(ValueError, match=r'Invalid|Next'):
            validate_timing(bad)
        conn.execute(
            'UPDATE seerapi_metadata SET value=?',
            (json.dumps(dict(state['official_update_timing'], last_update=None)),),
        )
        with pytest.raises(ValueError, match='differs from frozen'):
            validate_published_timing(conn, frozen)


def test_actions_summary_reports_unknown_next_and_cost_quality(tmp_path, capsys):
    with sqlite3.connect(':memory:') as conn:
        conn.execute(
            'CREATE TABLE seerapi_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)'
        )
        conn.executemany(
            'INSERT INTO seerapi_metadata VALUES(?,?)',
            [
                (
                    'official_update_timing',
                    json.dumps(
                        select_cycle([completed()], {}, clock())[
                            'official_update_timing'
                        ]
                    ),
                ),
                ('peak_cost_pool_time_anomalies', json.dumps({'items': [{}] * 4})),
            ],
        )
        summary, output = tmp_path / 'summary.md', tmp_path / 'output'
        release_summary(conn, summary=summary, output=output)
    assert '官方暂未公布' in summary.read_text('utf-8')
    assert '不是实际开服时间' in summary.read_text('utf-8')
    assert '配额时间区间不可信' in summary.read_text('utf-8')
    assert output.read_text().strip() == 'peak_time_anomaly_count=4'
    assert '::warning::' in capsys.readouterr().out


def test_ci_checks_new_regressions_and_freezes_cost_sources():
    root = Path(__file__).parents[1]
    workflow = (root / '.github/workflows/build-seerapi-data-db.yml').read_text('utf-8')
    assert 'pvpCostMode_cost.json activityTimeUpdateConfig.json' in workflow
    assert '--official-package-cache-dir .cache/official-packages' in workflow
    assert (
        '--maintenance-state .cache/official-packages/maintenance-cycle.json'
        in workflow
    )
    ci = (root / '.github/workflows/ci.yml').read_text('utf-8')
    assert 'tests/test_official_update_timing.py' in ci
    assert 'tests/test_release_peak_sources.py' in ci
