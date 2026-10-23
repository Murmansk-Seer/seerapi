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


def _completed_update_notice(item: dict) -> dict | None:
    if item.get('type') != 2:
        return None
    title = str(item.get('page_title', '') or item.get('main_title', ''))
    if '维护' not in title:
        return None
    body = re.sub(r'<[^>]*>', '', unescape(str(item.get('text', ''))))
    completed = _COMPLETED_MAINTENANCE.search(body)
    if completed is None:
        return None
    published = item.get('start')
    if isinstance(published, bool) or not isinstance(published, (int, float)):
        raise ValueError('completed maintenance announcement has invalid timestamp')
    observed = datetime.fromtimestamp(published, LOCAL_TZ)
    month, day = int(completed['month']), int(completed['day'])
    if (
        (month, day) != (observed.month, observed.day)
        or (completed['year'] and int(completed['year']) != observed.year)
        or re.search(rf'(?<!\d){month}月{day}日(?!\d)', title) is None
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
    notices = dict(previous.get('notices', {}))
    if not isinstance(document, list):
        raise ValueError('official maintenance response must be a list')
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
        notices[lower] = {
            'start': lower,
            'end': upper,
            'source': NOTICE_URL,
            'notice_id': str(item.get('id', '')),
        }
    precise_days = {
        datetime.fromisoformat(value['start']).astimezone(LOCAL_TZ).date()
        for value in notices.values()
        if value.get('start_basis') != 'completed_update_announcement'
    }
    notices = {
        key: value
        for key, value in notices.items()
        if value.get('start_basis') != 'completed_update_announcement'
        or datetime.fromisoformat(value['start']).astimezone(LOCAL_TZ).date()
        not in precise_days
    }
    for item in document:
        if not isinstance(item, dict):
            continue
        announcement = _completed_update_notice(item)
        if announcement is not None and (
            datetime.fromisoformat(announcement['start']).date() not in precise_days
        ):
            notices[announcement['start']] = announcement
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
    return {'notices': notices, 'current': current}


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
    if state['current'] is None:
        parser.error('no confirmed maintenance batch; refusing publication')
    current = state['current'] or {}
    outputs = {
        'maintenance_start': current.get('start', ''),
        'maintenance_end': current.get('end', ''),
        'maintenance_source': current.get('source', ''),
        'maintenance_notice_id': current.get('notice_id', ''),
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
