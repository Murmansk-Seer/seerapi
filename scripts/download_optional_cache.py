"""Only an explicit 404 permits an absent cache; corrupt downloads fail closed."""
import argparse
from pathlib import Path
import sqlite3

from release_api_data_source import DownloadNotFoundError, download_with_retries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        download_with_retries(args.url, args.output, accept='application/octet-stream', validate_sqlite=True)
    except DownloadNotFoundError:
        args.output.unlink(missing_ok=True)
        print('Optional cache explicitly unavailable (404); rebuilding without it.')
        return
    with sqlite3.connect(f'file:{args.output.resolve().as_posix()}?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Downloaded cache failed SQLite integrity_check')


if __name__ == '__main__':
    main()
