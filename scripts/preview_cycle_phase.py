"""Classify a verified official preview window for the release scheduler."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone


def preview_cycle_phase(start: str, end: str, now: datetime) -> str:
    lower = datetime.fromisoformat(start)
    upper = datetime.fromisoformat(end)
    if lower.tzinfo is None or upper.tzinfo is None or now.tzinfo is None:
        raise ValueError('preview window timestamps must have a timezone')
    if lower >= upper:
        raise ValueError('preview window end must follow start')
    if now < lower:
        return 'scheduled'
    if now >= upper:
        return 'expired'
    return 'active'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('start')
    parser.add_argument('end')
    args = parser.parse_args()
    print(  # noqa: T201 - consumed by the release workflow.
        preview_cycle_phase(args.start, args.end, datetime.now(timezone.utc))
    )


if __name__ == '__main__':
    main()
