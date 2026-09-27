from pathlib import Path
import sqlite3
import sys

SCRIPTS = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from preview_cycle_baseline import (
    baseline_asset_name,
    candidate_assets,
    is_pre_window_snapshot,
)

START = '2026-09-24T10:00:00+08:00'


def _snapshot(path: Path, generated_at: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            'CREATE TABLE new_content_release (id INTEGER PRIMARY KEY, generated_at TEXT)'
        )
        connection.execute(
            'INSERT INTO new_content_release VALUES (1, ?)', (generated_at,)
        )


def test_history_selection_uses_official_window_not_friday() -> None:
    history = {'assets': [
        {'name': 'seerapi-data-20260924015959.sqlite'},
        {'name': 'seerapi-data-20260924020000.sqlite'},
        {'name': 'seerapi-data-20260918180640.sqlite'},
    ]}
    assert candidate_assets(history, START) == [
        'seerapi-data-20260924015959.sqlite',
        'seerapi-data-20260918180640.sqlite',
    ]
    assert baseline_asset_name(START) == 'baseline-1790215200.sqlite'


def test_snapshot_must_have_been_published_before_window(tmp_path: Path) -> None:
    previous = tmp_path / 'previous.sqlite'
    at_boundary = tmp_path / 'boundary.sqlite'
    _snapshot(previous, '2026-09-24T01:59:59+00:00')
    _snapshot(at_boundary, '2026-09-24T02:00:00+00:00')
    assert is_pre_window_snapshot(previous, START)
    assert not is_pre_window_snapshot(at_boundary, START)
    assert not is_pre_window_snapshot(tmp_path / 'missing.sqlite', START)
