from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_peak_sources import (
    parse_official_peak,
    parse_official_peak_records,
    replace_official_peak,
    validate_official_peak_source,
)

VERSION = '20261113190033'
SOURCE = 'https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/08dfdb04c492b4a26d0547bae5b585d0'
REAL_ROWS = json.loads(
    (Path(__file__).parent / 'fixtures/official_peak_cost_20261113.json').read_text(
        'utf-8'
    )
)['item']
SEASON = {'id': 1, 'beginning': '2026_10_16 10:00:00', 'ending': '2027_1_8 10:00:00'}


def publish(conn, data):
    replace_official_peak(conn, data, source_version=VERSION, source_url=SOURCE)


def text(value: str) -> bytes:
    raw = value.encode()
    return struct.pack('<H', len(raw)) + raw


def activity(begin='2026_10_16 10:00:00', end='2027_1_8 10:00:00') -> bytes:
    return (
        struct.pack('<?i', True, 1)
        + text(begin)
        + text(end)
        + struct.pack('<i', 1)
        + text('season')
        + struct.pack('<4i', 12, 0, 0, 0)
        + text('')
    )


def costs(season=20261016, month=1020261016, pets='700001') -> bytes:
    return (
        struct.pack('<?iii', True, 1, 35, 1)
        + text('pool')
        + text(pets)
        + struct.pack('<ii', month, season)
        + text('2026_10_23 10:00:00')
    )


def test_common_season_and_cost_rotation_remain_distinct() -> None:
    data = parse_official_peak(activity(), costs())
    assert data.start.strftime('%Y%m%d') == '20261016'
    assert data.end.strftime('%Y%m%d') == '20270108'
    assert data.pools[0].end.strftime('%Y%m%d') == '20261023'
    assert data.pools[0].pets == (700001,)


@pytest.mark.parametrize('payload', [costs(season=20260904), costs(month=1020261309)])
def test_inconsistent_package_cannot_publish(payload: bytes) -> None:
    with pytest.raises(ValueError, match=r'inconsistent|invalid'):
        parse_official_peak(activity(), payload)


def test_publication_replaces_stale_season_and_pool_with_utc_storage() -> None:
    conn = sqlite3.connect(':memory:')
    conn.executescript("""
        CREATE TABLE peak_season(id INTEGER, start_time TEXT, end_time TEXT);
        CREATE TABLE peak_cost_pool(id INTEGER, cost INTEGER, name TEXT, start_time TEXT, end_time TEXT);
        CREATE TABLE pet(id INTEGER, peak_cost_pool_id INTEGER);
        INSERT INTO pet VALUES(700001,8);
        INSERT INTO peak_cost_pool VALUES(8,8,'old','old','old');
        INSERT INTO peak_season VALUES(1,'old','old');
    """)
    with conn:
        publish(conn, parse_official_peak(activity(), costs()))
    row = conn.execute('SELECT start_time,end_time FROM peak_season').fetchone()
    assert datetime.fromisoformat(row[0]) == datetime(2026, 10, 16, 2)
    assert datetime.fromisoformat(row[1]) == datetime(2027, 1, 8, 2)
    assert conn.execute('SELECT peak_cost_pool_id FROM pet').fetchone() == (35,)
    with pytest.raises(ValueError, match='unpublished pet'), conn:
        publish(conn, parse_official_peak(activity(), costs(pets='700002')))
    assert conn.execute('SELECT peak_cost_pool_id FROM pet').fetchone() == (35,)
    conn.close()


@contextmanager
def official_database(tmp_path, rows=None):
    rows = REAL_ROWS if rows is None else rows
    source = tmp_path / 'unity'
    source.mkdir()
    (source / 'pvpCostMode_cost.json').write_text(
        json.dumps({'item': rows}), encoding='utf-8'
    )
    (source / 'activityTimeUpdateConfig.json').write_text(
        json.dumps({'root': {'item': [SEASON]}}), encoding='utf-8'
    )
    (source / '.version').write_text(VERSION)
    data = parse_official_peak_records([SEASON], rows)
    conn = sqlite3.connect(':memory:')
    conn.executescript(
        'CREATE TABLE peak_season(id INTEGER,start_time TEXT,end_time TEXT); CREATE TABLE peak_cost_pool(id INTEGER,cost INTEGER,name TEXT,start_time TEXT,end_time TEXT); CREATE TABLE pet(id INTEGER PRIMARY KEY,peak_cost_pool_id INTEGER);'
    )
    conn.executemany(
        'INSERT INTO pet(id) VALUES(?)',
        [(pet,) for pool in data.pools for pet in pool.pets],
    )
    publish(conn, data)
    conn.executemany(
        'INSERT INTO seerapi_metadata VALUES(?,?)',
        [('config_package_version', VERSION), ('config_bundle_url', SOURCE)],
    )
    conn.commit()
    try:
        yield conn, data
    finally:
        conn.close()


def test_real_current_cost_rows_are_preserved_not_fixed_or_omitted(tmp_path):
    with official_database(tmp_path) as (conn, data):
        assert len(data.source_rows) == 5
        assert len(data.pools) == len(data.time_anomalies) == 4
        assert {pool.cost for pool in data.pools} == {35, 20, 10, 6}
        assert all(pool.start > pool.end for pool in data.pools)
        raw = json.loads(
            conn.execute(
                "SELECT value FROM seerapi_metadata WHERE key='peak_cost_pool_source'"
            ).fetchone()[0]
        )
        assert raw['rows'] == REAL_ROWS
        assert raw['source'] == SOURCE
        assert raw['config_version'] == VERSION
        assert (
            validate_official_peak_source(conn, tmp_path, expected_source_url=SOURCE)
            == 4
        )


@pytest.mark.parametrize(
    'tamper',
    [
        'omit_mark',
        'fake_mark',
        'fix_date',
        'source_row',
        'omit_pool',
        'pet_link',
        'source_version',
        'source_url',
    ],
)
def test_source_contract_rejects_tampering(tmp_path, tamper):
    with official_database(tmp_path) as (conn, _):
        if tamper in {'omit_mark', 'fake_mark'}:
            key = 'peak_cost_pool_time_anomalies'
            doc = json.loads(
                conn.execute(
                    'SELECT value FROM seerapi_metadata WHERE key=?', (key,)
                ).fetchone()[0]
            )
            if tamper == 'omit_mark':
                doc['items'].pop()
            else:
                doc['items'][0]['cost'] = 999
            conn.execute(
                'UPDATE seerapi_metadata SET value=? WHERE key=?',
                (json.dumps(doc), key),
            )
        elif tamper == 'fix_date':
            conn.execute(
                "UPDATE peak_cost_pool SET end_time='2026-12-01 02:00:00.000000' WHERE cost=35"
            )
        elif tamper == 'source_row':
            key = 'peak_cost_pool_source'
            doc = json.loads(
                conn.execute(
                    'SELECT value FROM seerapi_metadata WHERE key=?', (key,)
                ).fetchone()[0]
            )
            doc['rows'][0]['time'] = '2026_12_1 10:00:00'
            conn.execute(
                'UPDATE seerapi_metadata SET value=? WHERE key=?',
                (json.dumps(doc), key),
            )
        elif tamper == 'omit_pool':
            conn.execute('DELETE FROM peak_cost_pool WHERE cost=35')
        elif tamper == 'pet_link':
            conn.execute('UPDATE pet SET peak_cost_pool_id=NULL WHERE id=5000')
        else:
            key = (
                'config_package_version'
                if tamper == 'source_version'
                else 'config_bundle_url'
            )
            conn.execute(
                'UPDATE seerapi_metadata SET value=? WHERE key=?', ('forged', key)
            )
        with pytest.raises(ValueError, match=r'differs|differ'):
            validate_official_peak_source(conn, tmp_path, expected_source_url=SOURCE)


def test_corrected_official_dates_clear_stale_anomaly_markers(tmp_path):
    with official_database(tmp_path) as (conn, _):
        corrected = [dict(row, time='2026_12_11 10:00:00') for row in REAL_ROWS]
        (tmp_path / 'unity/pvpCostMode_cost.json').write_text(
            json.dumps({'item': corrected})
        )
        publish(conn, parse_official_peak_records([SEASON], corrected))
        assert (
            validate_official_peak_source(conn, tmp_path, expected_source_url=SOURCE)
            == 0
        )
        assert (
            json.loads(
                conn.execute(
                    "SELECT value FROM seerapi_metadata WHERE key='peak_cost_pool_time_anomalies'"
                ).fetchone()[0]
            )['items']
            == []
        )


@pytest.mark.parametrize(
    'change',
    [
        {'time': '2026_02_29 10:00:00'},
        {'cost': -1},
        {'subkeyMonth': 1020261301},
        {'subkeyTotal': 20260904},
        {'pet': '5000;5000'},
        {'pet': 'not-a-pet'},
    ],
)
def test_other_source_errors_remain_fatal(change):
    with pytest.raises(ValueError, match=r'.+'):
        parse_official_peak_records(
            [SEASON], [dict(REAL_ROWS[0], **change), *REAL_ROWS[1:]]
        )


def test_zero_length_range_is_explicitly_marked():
    row = dict(REAL_ROWS[0], time='2026_11_13 10:00:00')
    data = parse_official_peak_records([SEASON], [row])
    assert data.pools[0].start == data.pools[0].end
    assert data.time_anomalies[0]['code'] == 'invalid_time_range'


@pytest.mark.parametrize(
    'raw', [costs() + b'\x00', costs()[:-1], b'\x01\xff\xff\xff\xff', b'\x00\x00']
)
def test_malformed_wire_data_is_not_a_time_anomaly(raw):
    with pytest.raises((ValueError, IndexError), match=r'.+'):
        parse_official_peak(activity(), raw)


def test_duplicate_ids_costs_and_cross_pool_pet_assignments_remain_fatal():
    for change in (
        {'id': REAL_ROWS[0]['id']},
        {'cost': REAL_ROWS[0]['cost']},
        {'pet': REAL_ROWS[0]['pet']},
    ):
        with pytest.raises(ValueError, match='duplicate'):
            parse_official_peak_records(
                [SEASON], [REAL_ROWS[0], dict(REAL_ROWS[1], **change)]
            )
