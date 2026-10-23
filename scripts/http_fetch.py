"""Fetch required workflow resources with one bounded, complete-download retry layer."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import tempfile

from release_api_data_source import download_with_retries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('--output', type=Path)
    parser.add_argument('-H', '--header', action='append', default=[])
    parser.add_argument('--md5')
    args = parser.parse_args()
    if args.md5 is not None and re.fullmatch(r'[0-9a-fA-F]{32}', args.md5) is None:
        parser.error('invalid expected MD5')
    with tempfile.TemporaryDirectory(prefix='seerapi-fetch-') as directory:
        output = args.output or Path(directory) / 'response'
        download_with_retries(
            args.url,
            output,
            accept='*/*',
            extra_headers=args.header,
            expected_md5=args.md5.lower() if args.md5 else None,
        )
        if args.output is None:
            sys.stdout.buffer.write(output.read_bytes())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
