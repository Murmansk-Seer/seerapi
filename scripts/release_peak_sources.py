# SPDX-License-Identifier: MIT
"""Peak season and cost pools from the same verified official ConfigPackage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from solaris.parse.bytes_reader import BytesReader
from solaris.parse.parsers.activity_time_update_config import (
    ActivityTimeUpdateConfigParser,
)
from solaris.parse.parsers.pvp_cost_mode_cost import PvpCostModeCostParser
from solaris.utils import CN_TZ, parse_unity_datetime

if __package__:
    from .release_metadata import replace_release_metadata
else:
    from release_metadata import replace_release_metadata


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
    source_rows: tuple[dict[str, Any], ...]
    time_anomalies: tuple[dict[str, Any], ...]


def parse_official_peak(activity: bytes, costs: bytes) -> OfficialPeakData:
    reader = BytesReader(costs)
    if reader.ReadBoolean():
        count = reader.ReadSignedInt()
        if count < 0 or count > reader.remaining() // 22:
            raise ValueError('pvpCostMode_cost: invalid record count')
        for _ in range(count):
            reader.ReadSignedInt()
            reader.ReadSignedInt()
            reader.ReadUTFBytesWithLength()
            reader.ReadUTFBytesWithLength()
            reader.ReadSignedInt()
            reader.ReadSignedInt()
            reader.ReadUTFBytesWithLength()
    if not reader.eof():
        raise ValueError(
            f'pvpCostMode_cost: unconsumed bytes at offset={reader.position}'
        )
    records = ActivityTimeUpdateConfigParser().parse(activity)['root']['item']
    return parse_official_peak_records(
        records, PvpCostModeCostParser().parse(costs)['item']
    )


def parse_official_peak_records(
    records: Sequence[Mapping[str, Any]], cost_records: Sequence[Mapping[str, Any]]
) -> OfficialPeakData:
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
    seen_ids: set[int] = set()
    seen_pets: set[int] = set()
    anomalies = []
    for item in cost_records:
        if set(item) != {
            'id',
            'cost',
            'subkeyMonth',
            'subkeyTotal',
            'name',
            'pet',
            'time',
        }:
            raise ValueError('pvpCostMode_cost: unknown or missing official fields')
        if any(type(item[key]) is not str for key in ('name', 'pet', 'time')):
            raise ValueError('pvpCostMode_cost: invalid string field')
        for key in ('id', 'cost', 'subkeyMonth', 'subkeyTotal'):
            if type(item[key]) is not int:
                raise ValueError(f'pvpCostMode_cost: id={item.get("id")} invalid {key}')
        if item['id'] <= 0 or item['id'] in seen_ids:
            raise ValueError('Official cost pools have invalid or duplicate IDs')
        seen_ids.add(item['id'])
        if item['subkeyTotal'] != common_key:
            raise ValueError('Master and common peak seasons are inconsistent')
        cost = item['cost']
        if cost < 0 or cost in seen:
            raise ValueError('Official cost pools have invalid or duplicate costs')
        seen.add(cost)
        month_key = item['subkeyMonth'] - 1_000_000_000
        try:
            if not re.fullmatch(r'[0-9]{8}', str(month_key)):
                raise ValueError('Invalid date key width')
            pool_start = datetime.strptime(str(month_key), '%Y%m%d').replace(
                hour=10, tzinfo=CN_TZ
            )
            pool_end = parse_unity_datetime(item['time'])
        except ValueError as error:
            raise ValueError(
                f'pvpCostMode_cost id={item["id"]}: invalid date fields subkeyMonth={item["subkeyMonth"]!r}, time={item["time"]!r}: {error}'
            ) from error
        if cost == 0:
            continue
        # A parseable contradiction is an official source fact, not a valid
        # interval. Publish it only with source-bound, independently checked
        # anomaly metadata; all other parse/reference errors remain fatal.
        if pool_start >= pool_end:
            anomalies.append(
                {
                    'code': 'invalid_time_range',
                    'id': item['id'],
                    'cost': cost,
                    'subkeyMonth': item['subkeyMonth'],
                    'time': item['time'],
                    'mapped_start': pool_start.isoformat(),
                    'mapped_end': pool_end.isoformat(),
                }
            )
        pets = tuple(int(value) for value in item['pet'].split(';') if value)
        if (
            any(pet <= 0 for pet in pets)
            or len(set(pets)) != len(pets)
            or seen_pets.intersection(pets)
        ):
            raise ValueError(
                'Official cost pools have invalid or duplicate pet assignments'
            )
        seen_pets.update(pets)
        pools.append(
            OfficialCostPool(
                cost,
                item['name'],
                pool_start,
                pool_end,
                pets,
            )
        )
    if not pools:
        raise ValueError('Official master cost pools are empty')
    return OfficialPeakData(
        start,
        end,
        tuple(pools),
        tuple(dict(row) for row in cost_records),
        tuple(anomalies),
    )


def peak_source_metadata(
    data: OfficialPeakData, version: str, source: str
) -> dict[str, str]:
    raw = json.dumps(
        data.source_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
        allow_nan=False,
    )
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return {
        'peak_cost_pool_source': json.dumps(
            {
                'schema_version': 1,
                'config_version': version,
                'source': source,
                'sha256': digest,
                'rows': data.source_rows,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        'peak_cost_pool_time_anomalies': json.dumps(
            {
                'schema_version': 1,
                'source_sha256': digest,
                'items': data.time_anomalies,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def verified_peak_source_url(cache: Path, version: str) -> str:
    if not re.fullmatch(r'[0-9]{14}', version):
        raise ValueError('Invalid frozen ConfigPackage version')
    if __package__:
        from .config_package_sources import parse_package_manifest
    else:
        from config_package_sources import parse_package_manifest
    root = cache / 'ConfigPackage'
    manifest = parse_package_manifest(
        (root / f'PackageManifest_ConfigPackage_{version}.bytes').read_bytes()
    )
    bundle = next(
        (item for item in manifest.bundles if item.name == 'pgame_configs_bytes'), None
    )
    if bundle is None:
        raise ValueError('Frozen official ConfigPackage is missing config bundle')
    if not re.fullmatch(r'[0-9a-f]{32}', bundle.file_hash) or bundle.file_size < 0:
        raise ValueError('Invalid frozen ConfigPackage bundle identity')
    raw = (root / bundle.file_hash).read_bytes()
    if len(raw) != bundle.file_size or hashlib.md5(raw).hexdigest() != bundle.file_hash:
        raise ValueError('Frozen official ConfigPackage bundle failed integrity check')
    return (
        'https://newseer.61.com/Assets/StandaloneWindows64/ConfigPackage/'
        + bundle.file_hash
    )


def validate_official_peak_source(
    conn: sqlite3.Connection, source_dir: Path, *, expected_source_url: str
) -> int:
    root = source_dir / 'unity'
    data = parse_official_peak_records(
        json.loads((root / 'activityTimeUpdateConfig.json').read_text('utf-8'))['root'][
            'item'
        ],
        json.loads((root / 'pvpCostMode_cost.json').read_text('utf-8'))['item'],
    )
    metadata = dict(conn.execute('SELECT key,value FROM seerapi_metadata'))
    version = (root / '.version').read_text('utf-8').strip()
    if (
        metadata['config_package_version'] != version
        or metadata['config_bundle_url'] != expected_source_url
    ):
        raise ValueError(
            'Cost source version or URL differs from verified official binding'
        )
    expected = peak_source_metadata(data, version, expected_source_url)
    for key, value in expected.items():
        if key not in metadata or json.loads(metadata[key]) != json.loads(value):
            raise ValueError(f'{key} differs from frozen official source')
    actual_pools = set(
        conn.execute('SELECT id,cost,name,start_time,end_time FROM peak_cost_pool')
    )
    expected_pools = {
        (pool.cost, pool.cost, pool.name, _sql_time(pool.start), _sql_time(pool.end))
        for pool in data.pools
    }
    if actual_pools != expected_pools:
        raise ValueError('Cost pools differ from frozen official source')
    actual_pets = set(
        conn.execute(
            'SELECT id,peak_cost_pool_id FROM pet WHERE peak_cost_pool_id IS NOT NULL'
        )
    )
    expected_pets = {(pet, pool.cost) for pool in data.pools for pet in pool.pets}
    if actual_pets != expected_pets:
        raise ValueError('Cost pet assignments differ from frozen official source')
    if list(conn.execute('SELECT id,start_time,end_time FROM peak_season')) != [
        (1, _sql_time(data.start), _sql_time(data.end))
    ]:
        raise ValueError('Peak season differs from frozen official source')
    return len(data.time_anomalies)


def _sql_time(value: datetime) -> str:
    # Published ORM datetime storage is UTC without an offset.
    return (
        value.astimezone(timezone.utc)
        .replace(tzinfo=None)
        .isoformat(sep=' ', timespec='microseconds')
    )


def replace_official_peak(
    conn: sqlite3.Connection,
    data: OfficialPeakData,
    *,
    source_version: str,
    source_url: str,
) -> None:
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
    replace_release_metadata(
        conn, peak_source_metadata(data, source_version, source_url)
    )
