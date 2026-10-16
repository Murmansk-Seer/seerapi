from datetime import datetime
from pathlib import Path
import sqlite3
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from release_peak_sources import parse_official_peak, replace_official_peak


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


@pytest.mark.parametrize('payload', [costs(season=20260904), costs(month=1020270109)])
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
        replace_official_peak(conn, parse_official_peak(activity(), costs()))
    row = conn.execute('SELECT start_time,end_time FROM peak_season').fetchone()
    assert datetime.fromisoformat(row[0]) == datetime(2026, 10, 16, 2)
    assert datetime.fromisoformat(row[1]) == datetime(2027, 1, 8, 2)
    assert conn.execute('SELECT peak_cost_pool_id FROM pet').fetchone() == (35,)
    with pytest.raises(ValueError, match='unpublished pet'), conn:
        replace_official_peak(
            conn, parse_official_peak(activity(), costs(pets='700002'))
        )
    assert conn.execute('SELECT peak_cost_pool_id FROM pet').fetchone() == (35,)
    conn.close()
