# SPDX-License-Identifier: MIT
"""Peak season and cost pools from the same verified official ConfigPackage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3

from solaris.parse.parsers.activity_time_update_config import (
    ActivityTimeUpdateConfigParser,
)
from solaris.parse.parsers.pvp_cost_mode_cost import PvpCostModeCostParser
from solaris.utils import CN_TZ, parse_unity_datetime


@dataclass(frozen=True)
class OfficialCostPool:
    cost: int
    name: str
    start: datetime
    end: datetime
    pets: tuple[int, ...]


@dataclass(frozen=True)
class OfficialPeakData:
    start: datetime
    end: datetime
    pools: tuple[OfficialCostPool, ...]


def parse_official_peak(activity: bytes, costs: bytes) -> OfficialPeakData:
    records = ActivityTimeUpdateConfigParser().parse(activity)['root']['item']
    seasons = [item for item in records if item['id'] == 1]
    if len(seasons) != 1:
        raise ValueError('Official peak season must have exactly one record')
    season = seasons[0]
    start = parse_unity_datetime(season['beginning'])
    end = parse_unity_datetime(season['ending'])
    if start >= end:
        raise ValueError('Official peak season has invalid boundaries')
    common_key = int(start.strftime('%Y%m%d'))
    pools = []
    seen: set[int] = set()
    for item in PvpCostModeCostParser().parse(costs)['item']:
        if item['subkeyTotal'] != common_key:
            raise ValueError('Master and common peak seasons are inconsistent')
        cost = item['cost']
        if cost == 0:
            continue
        if cost < 0 or cost in seen:
            raise ValueError('Official cost pools have invalid or duplicate costs')
        seen.add(cost)
        month_key = item['subkeyMonth'] - 1_000_000_000
        pool_start = datetime.strptime(str(month_key), '%Y%m%d').replace(
            hour=10, tzinfo=CN_TZ
        )
        pool_end = parse_unity_datetime(item['time'])
        if pool_start >= pool_end:
            raise ValueError('Official cost pool has invalid boundaries')
        pools.append(
            OfficialCostPool(
                cost,
                item['name'],
                pool_start,
                pool_end,
                tuple(int(value) for value in item['pet'].split(';') if value),
            )
        )
    if not pools:
        raise ValueError('Official master cost pools are empty')
    return OfficialPeakData(start, end, tuple(pools))


def _sql_time(value: datetime) -> str:
    # Published ORM datetime storage is UTC without an offset.
    return (
        value.astimezone(timezone.utc)
        .replace(tzinfo=None)
        .isoformat(sep=' ', timespec='microseconds')
    )


def replace_official_peak(conn: sqlite3.Connection, data: OfficialPeakData) -> None:
    conn.execute('DELETE FROM peak_season')
    conn.execute(
        'INSERT INTO peak_season(id,start_time,end_time) VALUES(1,?,?)',
        (_sql_time(data.start), _sql_time(data.end)),
    )
    conn.execute('UPDATE pet SET peak_cost_pool_id=NULL')
    conn.execute('DELETE FROM peak_cost_pool')
    for pool in data.pools:
        conn.execute(
            'INSERT INTO peak_cost_pool(id,cost,name,start_time,end_time) VALUES(?,?,?,?,?)',
            (
                pool.cost,
                pool.cost,
                pool.name,
                _sql_time(pool.start),
                _sql_time(pool.end),
            ),
        )
        for pet in pool.pets:
            if (
                conn.execute(
                    'UPDATE pet SET peak_cost_pool_id=? WHERE id=?', (pool.cost, pet)
                ).rowcount
                != 1
            ):
                raise ValueError(
                    f'Official master pool references an unpublished pet: {pet}'
                )
