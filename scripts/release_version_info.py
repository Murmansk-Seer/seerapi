"""Report release schema and cycle versions for the database build workflow."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3

from new_content_index_models import SEMANTIC_SCHEMA_VERSION
from new_content_index_release import RELEASE_TABLE, _config_version
from new_content_index_snapshot import _table_columns


def release_version_info(
    previous_db: Path, current_db: Path, current_cycle: str
) -> tuple[int, int, str, str, str, str]:
    with sqlite3.connect(previous_db) as connection:
        columns = _table_columns(connection, RELEASE_TABLE)
        previous_schema = 1
        previous_version = _config_version(connection)
        previous_cycle = 'unknown'
        if 'schema_version' in columns:
            fields = 'schema_version, weekly_cycle' if 'weekly_cycle' in columns else 'schema_version'
            row = connection.execute(
                f'SELECT {fields} FROM {RELEASE_TABLE} WHERE id = 1'
            ).fetchone()
            if row is not None:
                previous_schema = int(row[0])
                if 'weekly_cycle' in columns:
                    previous_cycle = str(row[1] or previous_cycle)
    with sqlite3.connect(current_db) as connection:
        current_version = _config_version(connection)
    return (
        SEMANTIC_SCHEMA_VERSION,
        previous_schema,
        previous_version,
        previous_cycle,
        current_version,
        current_cycle,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('previous_db', type=Path)
    parser.add_argument('current_db', type=Path)
    parser.add_argument('current_cycle')
    args = parser.parse_args()
    print(*release_version_info(args.previous_db, args.current_db, args.current_cycle))


if __name__ == '__main__':
    main()
