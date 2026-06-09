# SPDX-License-Identifier: MIT
"""Build alias SQLite database from CSV files under tables/.

Each CSV filename becomes a table name. Every CSV must contain ``name`` and
``target_id`` columns.

Usage:
    python scripts/build_alias_db.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = ROOT / "tables"
OUTPUT_DB = ROOT / "aliases-data.sqlite"


def main() -> None:
    OUTPUT_DB.unlink(missing_ok=True)

    conn = sqlite3.connect(OUTPUT_DB)
    try:
        for csv_file in sorted(TABLES_DIR.glob("*.csv")):
            table_name = csv_file.stem

            conn.execute(
                f"CREATE TABLE [{table_name}] "
                "(name TEXT NOT NULL, target_id INTEGER NOT NULL, "
                "PRIMARY KEY (name, target_id))"
            )

            with csv_file.open(encoding="utf-8-sig", newline="") as f:
                rows = [
                    (row["name"], int(row["target_id"]))
                    for row in csv.DictReader(f)
                    if row.get("name") and row.get("target_id")
                ]

            conn.executemany(
                f"INSERT INTO [{table_name}] (name, target_id) VALUES (?, ?)",
                rows,
            )
            print(f"{csv_file.name} -> {table_name}: {len(rows)} rows")

        conn.commit()
    finally:
        conn.close()

    size_kb = OUTPUT_DB.stat().st_size / 1024
    print(f"\nGenerated {OUTPUT_DB} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
