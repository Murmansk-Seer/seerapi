from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import pytest
from test_build_new_content_index import _create_database, indexer
from test_maintenance_cycle import _completed_notice

from scripts import maintenance_baseline as baseline
from scripts.maintenance_cycle import fingerprint, select_cycle


def clock(monkeypatch, value):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromisoformat(value).astimezone(tz)

    monkeypatch.setattr(indexer, 'datetime', Clock)


@pytest.mark.parametrize(
    ('title', 'body'),
    [
        ('10月09日维护', '于10月9日进行了每周例行更新维护'),
        ('10 月 <b>09</b> 日维护', '于 10 月 <b>9</b> 日 已完成 每周例行更新维护'),
        ('2026年10月09日维护', '于2026年10月9日完成了每周例行更新维护'),
    ],
)
def test_numeric_dates_accept_padding_spaces_and_html(title, body):
    notice = dict(
        _completed_notice(),
        page_title=title,
        text=body,
        start=datetime.fromisoformat('2026-10-09T11:00:00+08:00').timestamp(),
    )
    state = select_cycle(
        [notice], {}, datetime.fromisoformat('2026-10-09T18:00:00+08:00')
    )
    assert state['update_cycle_id'] == '2026-10-09'


@pytest.mark.parametrize(
    ('when', 'status'),
    [
        ('2026-10-29T23:59:59+08:00', 'confirmed'),
        ('2026-10-30T00:00:00+08:00', 'cycle_unavailable'),
        ('2026-10-29T16:00:00+00:00', 'cycle_unavailable'),
    ],
)
def test_seven_calendar_day_boundary_and_removed_notices(when, status):
    state = select_cycle(
        [_completed_notice()], {}, datetime.fromisoformat('2026-10-23T18:00:00+08:00')
    )
    later = select_cycle([], state, datetime.fromisoformat(when))
    assert later['status'] == status
    assert later['current'] == state['current']
    assert (fingerprint(later) != fingerprint(state)) == (status != 'confirmed')


def test_reused_id_new_date_advances_but_same_day_edit_keeps_identity():
    now = datetime.fromisoformat('2026-10-23T20:00:00+08:00')
    original = select_cycle([_completed_notice()], {}, now)
    changed = dict(
        _completed_notice(),
        start=datetime.fromisoformat('2026-10-23T19:00:00+08:00').timestamp(),
    )
    assert select_cycle([changed], original, now) == original
    later = dict(
        changed,
        page_title='10月30日维护',
        text='于10月30日进行了每周例行更新维护',
        start=datetime.fromisoformat('2026-10-30T11:00:00+08:00').timestamp(),
    )
    next_cycle = select_cycle(
        [later], original, datetime.fromisoformat('2026-10-30T18:00:00+08:00')
    )
    assert next_cycle['update_cycle_id'] == '2026-10-30'
    assert next_cycle['status'] == 'confirmed'


def test_conflicting_title_dates_are_rejected():
    notice = dict(_completed_notice(), page_title='10月23日/10月30日维护')
    state = select_cycle(
        [notice], {}, datetime.fromisoformat('2026-10-23T20:00:00+08:00')
    )
    assert state['current'] is None


def test_pending_publication_cannot_replace_confirmed_history():
    workflow = (
        Path(__file__).resolve().parents[1]
        / '.github/workflows/build-seerapi-data-db.yml'
    ).read_text()
    for name in (
        'Stage versioned historical data snapshot',
        'Publish versioned historical data snapshot',
        'Retain five historical data snapshots',
    ):
        block = workflow.split(f'- name: {name}', 1)[1].split('- name:', 1)[0]
        assert "if: ${{ steps.new_content.outputs.cycle_status == 'ready' }}" in block


def test_unconfirmed_future_observation_does_not_block_completed_evidence():
    early = datetime.fromisoformat('2026-10-23T09:00:00+08:00')
    future = dict(
        _completed_notice(),
        start=datetime.fromisoformat('2026-10-23T19:00:00+08:00').timestamp(),
    )
    saved = select_cycle([future], {}, early)
    assert saved['current'] is None
    confirmed = select_cycle(
        [_completed_notice()],
        saved,
        datetime.fromisoformat('2026-10-23T12:00:00+08:00'),
    )
    assert confirmed['current']['start'] == '2026-10-23T11:07:40+08:00'


def snapshot(path, stamp, status='ready'):
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE new_content_release(id INTEGER, generated_at TEXT)')
        conn.execute('INSERT INTO new_content_release VALUES (1,?)', (stamp,))
        conn.execute('CREATE TABLE new_content_source_snapshot(id INTEGER)')
        conn.execute('INSERT INTO new_content_source_snapshot VALUES (1)')
        conn.execute('CREATE TABLE seerapi_metadata(key TEXT, value TEXT)')
        conn.execute(
            'INSERT INTO seerapi_metadata VALUES (?,?)', ('update_cycle_status', status)
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(str(path) + '.sha256').write_text(digest)
    return digest


@pytest.mark.parametrize(
    ('stamp', 'status', 'accepted'),
    [
        ('2026-10-22T23:59:59+08:00', 'ready', True),
        ('2026-10-23T00:00:00+08:00', 'ready', False),
        ('2026-10-23T18:11:23+08:00', 'ready', False),
        ('2026-10-22T10:00:00+08:00', 'cycle_unavailable', False),
        ('2026-10-22T10:00:00+08:00', 'baseline_unavailable', False),
    ],
)
def test_baseline_uses_midnight_not_announcement_time(
    tmp_path, stamp, status, accepted
):
    path = tmp_path / 'candidate.sqlite'
    snapshot(path, stamp, status)
    result = baseline.verified_timestamp(
        path, Path(str(path) + '.sha256'), '2026-10-23T19:00:00+08:00'
    )
    assert (result is not None) == accepted


@pytest.mark.parametrize(
    ('day', 'epoch'), [('2026-10-09', 1791511200), ('2026-10-23', 1792724860)]
)
def test_legacy_pin_migrates_once_and_binding_is_immutable(
    tmp_path, monkeypatch, day, epoch
):
    asset = f'maintenance-{epoch}.sqlite'
    digest = snapshot(tmp_path / asset, f'{day}T00:00:00+09:00')
    assets = [asset, asset + '.sha256']
    uploads = []

    def gh(*args):
        if args[:2] == ('release', 'view'):
            assert args[2] == 'seerapi-maintenance-baselines'
            return json.dumps({'assets': [{'name': name} for name in assets]})
        if args[:2] == ('release', 'upload'):
            uploads.extend(args[3:-2])
        return ''

    monkeypatch.setattr(baseline, 'gh', gh)
    output = tmp_path / 'selected.sqlite'
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'baseline',
            '--start',
            f'{day}T19:00:00+08:00',
            '--output',
            str(output),
            '--repository',
            'test/repo',
        ],
    )
    baseline.main()
    binding_path = tmp_path / f'maintenance-{day}.json'
    binding = json.loads(binding_path.read_text())
    assert binding['sha256'] == digest
    assert binding['asset'] == asset
    assert uploads == [str(binding_path)]
    assets.append(binding_path.name)
    baseline.main()
    assert uploads == [str(binding_path)]
    binding['sha256'] = '0' * 64
    binding_path.write_text(json.dumps(binding))
    with pytest.raises(ValueError, match='binding checksum mismatch'):
        baseline.main()


def test_missing_baseline_does_not_choose_arbitrary_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, 'gh', lambda *args: json.dumps({'assets': []}))
    output = tmp_path / 'selected.sqlite'
    result = tmp_path / 'outputs'
    monkeypatch.setattr(
        sys,
        'argv',
        [
            'baseline',
            '--start',
            '2026-10-23T19:00:00+08:00',
            '--output',
            str(output),
            '--repository',
            'test/repo',
            '--github-output',
            str(result),
        ],
    )
    baseline.main()
    assert not output.exists()
    assert result.read_text() == 'baseline_available=false\n'


@pytest.mark.parametrize(
    ('when', 'with_baseline', 'status', 'count'),
    [
        ('2026-10-15T23:59:59+08:00', True, 'ready', 1),
        ('2026-10-16T00:00:00+08:00', True, 'cycle_unavailable', 0),
        ('2026-10-09T18:00:00+08:00', False, 'baseline_unavailable', 0),
    ],
)
def test_index_pending_and_missing_baseline_keep_normal_data(
    tmp_path, monkeypatch, when, with_baseline, status, count
):
    before, current = tmp_path / 'before.sqlite', tmp_path / 'current.sqlite'
    _create_database(before, version='20261008204457', pet_ids=(1,))
    indexer.write_release_state(
        before, indexer.build_release_state(before, None, 'before'), None
    )
    _create_database(current, version='20261009153137', pet_ids=(1, 2))
    clock(monkeypatch, when)
    args = [
        'index',
        '--current',
        str(current),
        '--previous',
        str(before),
        '--current-git-sha',
        'test',
        '--maintenance-mode',
        '--maintenance-start',
        '2026-10-09T10:00:00+08:00',
    ]
    if with_baseline:
        args += ['--baseline', str(before)]
    monkeypatch.setattr(sys, 'argv', args)
    indexer.main()
    with sqlite3.connect(current) as conn:
        metadata = dict(conn.execute('SELECT key,value FROM seerapi_metadata'))
        assert metadata['update_cycle_status'] == status
        assert metadata['update_cycle_id'] == '2026-10-09'
        assert (
            conn.execute('SELECT count(*) FROM new_content_item').fetchone()[0] == count
        )
        assert conn.execute('SELECT count(*) FROM pet').fetchone()[0] == 2
