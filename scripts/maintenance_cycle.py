"""Persist official maintenance batches independently from preview windows."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from zoneinfo import ZoneInfo

NOTICE_URL = 'https://unity-notice.61.com/unity_notice/'
LOCAL_TZ = ZoneInfo('Asia/Shanghai')


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
            isinstance(start, bool) or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float)) or end <= start
        ):
            raise ValueError('maintenance notice has invalid timestamps')
        lower = datetime.fromtimestamp(start, LOCAL_TZ).isoformat(timespec='seconds')
        upper = datetime.fromtimestamp(end, LOCAL_TZ).isoformat(timespec='seconds')
        notices[lower] = {
            'start': lower, 'end': upper,
            'source': NOTICE_URL, 'notice_id': str(item.get('id', '')),
        }
    eligible = [value for value in notices.values()
                if datetime.fromisoformat(value['start']) <= now]
    current = max(eligible, key=lambda value: datetime.fromisoformat(value['start'])) if eligible else None
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
        print(f'Maintenance source unavailable: {type(error).__name__}; preserving verified observations', file=sys.stderr)
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
    print(json.dumps(outputs, ensure_ascii=False))


if __name__ == '__main__':
    main()
