"""Public official maintenance evidence, not inferred game or cost deadlines."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3


def select_timing(observations: list[dict], previous: dict, now: datetime) -> dict:
    last = previous.get('last_update')
    future = []
    for item in sorted(observations, key=lambda value: value['start']):
        start = datetime.fromisoformat(item['start'])
        completed = item.get('start_basis') == 'completed_update_announcement'
        record = {
            'date': start.date().isoformat(),
            'planned_start': None if completed else item['start'],
            'planned_end': None if completed else item['end'],
            'completion_announced_at': item['start'] if completed else None,
            'status': 'completed_announced' if completed else 'maintenance_announced',
            'evidence': [
                {
                    'kind': 'completed_update_announcement'
                    if completed
                    else 'maintenance_notice',
                    'notice_id': item['notice_id'],
                    'source': item['source'],
                }
            ],
        }
        if start > now:
            if not completed:
                record['status'] = 'scheduled'
                future.append(record)
            continue
        if last is None or record['date'] > last['date']:
            last = record
        elif record['date'] == last['date']:
            last = dict(last)
            for key in ('planned_start', 'planned_end', 'completion_announced_at'):
                if key == 'completion_announced_at' and last[key] is not None:
                    continue  # Keep the first verified completed announcement.
                if record[key] is not None:
                    last[key] = record[key]
            if last['completion_announced_at'] is not None:
                last['status'] = 'completed_announced'
            evidence = {
                json.dumps(value, sort_keys=True): value
                for value in last['evidence'] + record['evidence']
            }
            last['evidence'] = [evidence[key] for key in sorted(evidence)]
    return {
        'schema_version': 1,
        'timezone': 'Asia/Shanghai',
        'last_update': last,
        # Only a fresh official response can announce the next maintenance.
        'next_update': min(
            future,
            key=lambda item: (item['planned_start'], json.dumps(item, sort_keys=True)),
        )
        if future
        else None,
    }


def validate_timing(value: object) -> dict:
    if (
        not isinstance(value, dict)
        or value.get('schema_version') != 1
        or value.get('timezone') != 'Asia/Shanghai'
    ):
        raise ValueError('Invalid official update timing contract')
    for key in ('last_update', 'next_update'):
        if key not in value:
            raise ValueError(f'Official update timing missing {key}')
        item = value[key]
        if item is None:
            continue
        if not isinstance(item, dict) or not item.get('evidence'):
            raise ValueError(f'Official update timing missing evidence: {key}')
        datetime.strptime(item['date'], '%Y-%m-%d')
        start, end = item['planned_start'], item['planned_end']
        if bool(start) != bool(end):
            raise ValueError('Official planned maintenance needs both boundaries')
        for stamp in (start, end, item['completion_announced_at']):
            if stamp is not None and datetime.fromisoformat(stamp).utcoffset() is None:
                raise ValueError('Official update timestamp requires timezone')
        if start and datetime.fromisoformat(start) >= datetime.fromisoformat(end):
            raise ValueError('Official planned maintenance has invalid boundaries')
        allowed = (
            {'scheduled'}
            if key == 'next_update'
            else {'maintenance_announced', 'completed_announced'}
        )
        if item['status'] not in allowed:
            raise ValueError('Invalid official update timing status')
        if (
            item['status'] == 'completed_announced'
            and item['completion_announced_at'] is None
        ):
            raise ValueError('Completion requires an explicit completed announcement')
        if key == 'next_update' and (
            not start or item['completion_announced_at'] is not None
        ):
            raise ValueError('Next maintenance must be a planned official window')
    return value


def timing_from_state(path: Path) -> dict:
    return validate_timing(
        json.loads(path.read_text('utf-8'))['official_update_timing']
    )


def validate_published_timing(
    conn: sqlite3.Connection, state: Path | None = None
) -> dict:
    row = conn.execute(
        "SELECT value FROM seerapi_metadata WHERE key='official_update_timing'"
    ).fetchone()
    if row is None:
        raise ValueError('Missing official update timing metadata')
    timing = validate_timing(json.loads(row[0]))
    if state is not None and timing != timing_from_state(state):
        raise ValueError(
            'Official update timing differs from frozen maintenance evidence'
        )
    return timing


def release_summary(
    conn: sqlite3.Connection, *, summary: Path | None, output: Path | None
) -> None:
    timing = validate_published_timing(conn)
    metadata = dict(conn.execute('SELECT key,value FROM seerapi_metadata'))
    anomalies = json.loads(metadata['peak_cost_pool_time_anomalies'])['items']
    last, upcoming = timing['last_update'], timing['next_update']
    last_text = (
        '暂无已确认公告'
        if last is None
        else (
            f'{last["date"]}（已完成公告确认；公告发布时间 {last["completion_announced_at"]}，不是实际开服时间）'
            if last['status'] == 'completed_announced'
            else f'{last["date"]}（已公告维护，未确认完成）'
        )
    )
    next_text = (
        '官方暂未公布'
        if upcoming is None
        else f'{upcoming["planned_start"]} 至 {upcoming["planned_end"]}（计划维护时段）'
    )
    quality = (
        f'{len(anomalies)} 项；保留官方原值，配额时间区间不可信。'
        if anomalies
        else '0 项；所有配额时间区间通过校验。'
    )
    if summary:
        with summary.open('a', encoding='utf-8') as stream:
            stream.write(
                f'\n## 官方更新时间与来源质量\n\n- 上次更新：{last_text}\n- 下次维护：{next_text}\n- 公告来源：https://unity-notice.61.com/unity_notice/\n- cost 时间异常：{quality}\n'
            )
    if output:
        with output.open('a', encoding='utf-8') as stream:
            stream.write(f'peak_time_anomaly_count={len(anomalies)}\n')
    if anomalies:
        print(
            f'::warning::官方 cost 配额时间区间不可信：{len(anomalies)} 项；原值与来源已严格核验，未猜测或修造日期。'
        )
