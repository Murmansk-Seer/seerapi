"""Persist official maintenance batches independently from preview windows."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import sys
from urllib.request import urlopen
from zoneinfo import ZoneInfo

NOTICE_URL = 'https://unity-notice.61.com/unity_notice/'
LOCAL_TZ = ZoneInfo('Asia/Shanghai')
_COMPLETED_MAINTENANCE = re.compile(
    r'(?:于|在)\s*(?:(?P<year>\d{4})年)?'
    r'(?P<month>\d{1,2})月(?P<day>\d{1,2})日\s*'
    r'(?:进行了|已完成|完成了)(?:每周)?(?:例行)?(?:更新)?维护'
)


def cycle_identity(start: str) -> str:
    stamp = datetime.fromisoformat(start)
    if stamp.tzinfo is None:
        raise ValueError('maintenance start requires a timezone')
    return stamp.astimezone(LOCAL_TZ).date().isoformat()


def cycle_status(start: str, now: datetime) -> str:
    stamp = datetime.fromisoformat(start)
    cycle_identity(start)
    if now < stamp:
        return 'scheduled'
    age = (now.astimezone(LOCAL_TZ).date() - stamp.astimezone(LOCAL_TZ).date()).days
    return 'cycle_unavailable' if age >= 7 else 'confirmed'


def _completed_update_notice(item: dict) -> dict | None:
    if item.get('type') != 2:
        return None
    title = re.sub(
        r'<[^>]*>',
        '',
        unescape(str(item.get('page_title', '') or item.get('main_title', ''))),
    )
    title = re.sub(r'\s+', '', title)
    if '维护' not in title:
        return None
    body = re.sub(r'<[^>]*>', '', unescape(str(item.get('text', ''))))
    body = re.sub(r'\s+', '', body)
    completed_dates = list(_COMPLETED_MAINTENANCE.finditer(body))
    if not completed_dates:
        return None
    completed = completed_dates[0]
    published = item.get('start')
    if isinstance(published, bool) or not isinstance(published, (int, float)):
        raise ValueError('completed maintenance announcement has invalid timestamp')
    observed = datetime.fromtimestamp(published, LOCAL_TZ)
    month, day = int(completed['month']), int(completed['day'])
    title_dates = list(
        re.finditer(
            r'(?<!\d)(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日',
            title,
        )
    )
    if (
        (month, day) != (observed.month, observed.day)
        or (completed['year'] and int(completed['year']) != observed.year)
        or not title_dates
        or not all(
            (int(match['month']), int(match['day'])) == (month, day)
            and (not match['year'] or int(match['year']) == observed.year)
            for match in (*title_dates, *completed_dates)
        )
    ):
        return None
    # This is evidence that the update completed, not its exact outage time.
    # The announcement expiry must not be presented as the maintenance end.
    return {
        'start': observed.isoformat(timespec='seconds'),
        'end': '',
        'source': NOTICE_URL,
        'notice_id': str(item.get('id', '')),
        'start_basis': 'completed_update_announcement',
    }


def select_cycle(document: object, previous: dict, now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError('maintenance selection requires an aware timestamp')
    # The first verified observation anchors each date, even when a notice is
    # edited or a more precise outage notice arrives later that same day.
    notices = {}
    values = list(previous.get('notices', {}).values())
    if previous.get('current'):
        values.insert(0, previous['current'])
    for value in values:
        notices.setdefault(cycle_identity(value['start']), dict(value))
    if not isinstance(document, list):
        raise ValueError('official maintenance response must be a list')

    def observe(value: dict) -> None:
        key = cycle_identity(value['start'])
        saved = notices.get(key)
        if saved is None or (
            datetime.fromisoformat(saved['start']) > now
            and datetime.fromisoformat(value['start']) <= now
        ):
            notices[key] = value

    for item in document:
        if not isinstance(item, dict) or item.get('type') != 3:
            continue
        start, end = item.get('start'), item.get('end')
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or end <= start
        ):
            raise ValueError('maintenance notice has invalid timestamps')
        lower = datetime.fromtimestamp(start, LOCAL_TZ).isoformat(timespec='seconds')
        upper = datetime.fromtimestamp(end, LOCAL_TZ).isoformat(timespec='seconds')
        observe(
            {
                'start': lower,
                'end': upper,
                'source': NOTICE_URL,
                'notice_id': str(item.get('id', '')),
            },
        )
    for item in document:
        if not isinstance(item, dict):
            continue
        announcement = _completed_update_notice(item)
        if announcement is not None:
            observe(announcement)
    eligible = [
        value
        for value in notices.values()
        if datetime.fromisoformat(value['start']) <= now
    ]
    current = (
        max(eligible, key=lambda value: datetime.fromisoformat(value['start']))
        if eligible
        else None
    )
    return {
        'notices': notices,
        'current': current,
        'update_cycle_id': cycle_identity(current['start']) if current else '',
        'status': cycle_status(current['start'], now)
        if current
        else 'cycle_unavailable',
    }


def fingerprint(state: dict) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    previous = json.loads(args.state.read_text()) if args.state.exists() else {}
    try:
        with urlopen(NOTICE_URL, timeout=20) as response:
            document = json.load(response)
        state = select_cycle(document, previous, datetime.now(timezone.utc))
    except (OSError, ValueError) as error:
        print(  # noqa: T201 - CLI diagnostic on stderr
            f'Maintenance source unavailable: {type(error).__name__}; preserving verified observations',
            file=sys.stderr,
        )
        state = select_cycle([], previous, datetime.now(timezone.utc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True))
    current = state['current'] or {}
    outputs = {
        'maintenance_start': current.get('start', ''),
        'maintenance_end': current.get('end', ''),
        'maintenance_source': current.get('source', ''),
        'maintenance_notice_id': current.get('notice_id', ''),
        'maintenance_cycle_id': state['update_cycle_id'],
        'maintenance_status': state['status'],
        'maintenance_hash': fingerprint(state),
        'maintenance_changed': str(fingerprint(previous) != fingerprint(state)).lower(),
    }
    if args.github_output:
        with args.github_output.open('a') as stream:
            for key, value in outputs.items():
                stream.write(f'{key}={value}\n')
    print(json.dumps(outputs, ensure_ascii=False))  # noqa: T201 - workflow output


if __name__ == '__main__':
    main()
