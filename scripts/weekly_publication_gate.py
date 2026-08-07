#!/usr/bin/env python3
"""Decide whether a weekly SeerAPI database publication must be deferred."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import re


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def weekly_cycle(version: str) -> str | None:
    """Return the Friday-starting cycle for a ConfigPackage version."""
    digits = "".join(character for character in version if character.isdigit())
    if len(digits) < 8:
        return None
    try:
        value = datetime.strptime(digits[:8], "%Y%m%d").date()
    except ValueError:
        return None
    friday = value - timedelta(days=(value.weekday() - 4) % 7)
    return friday.isoformat()


def should_defer(
    *,
    current_config_version: str,
    previous_config_version: str,
    current_api_data_sha256: str,
    previous_api_data_sha256: str,
) -> bool:
    """Protect a new weekly cycle from publication against an old api-data DB."""
    current_cycle = weekly_cycle(current_config_version)
    previous_cycle = weekly_cycle(previous_config_version)
    current_sha = current_api_data_sha256.strip().lower()
    previous_sha = previous_api_data_sha256.strip().lower()
    return bool(
        current_cycle
        and previous_cycle
        and current_cycle > previous_cycle
        and SHA256_PATTERN.fullmatch(current_sha)
        and current_sha == previous_sha
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-config-version", required=True)
    parser.add_argument("--previous-config-version", default="")
    parser.add_argument("--current-api-data-sha256", required=True)
    parser.add_argument("--previous-api-data-sha256", default="")
    parser.add_argument("--github-output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    defer = should_defer(
        current_config_version=args.current_config_version,
        previous_config_version=args.previous_config_version,
        current_api_data_sha256=args.current_api_data_sha256,
        previous_api_data_sha256=args.previous_api_data_sha256,
    )
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"defer={str(defer).lower()}\n")
            output.write(f"current_weekly_cycle={weekly_cycle(args.current_config_version) or ''}\n")
            output.write(f"previous_weekly_cycle={weekly_cycle(args.previous_config_version) or ''}\n")
    if defer:
        print("Deferred: waiting for api-data to catch up with the new weekly cycle")
    else:
        print("Weekly publication consistency gate passed")


if __name__ == "__main__":
    main()
