"""The scheduler must rebuild even when only the DLL window phase changes."""

from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from preview_cycle_phase import preview_cycle_phase


def test_phase_changes_at_exact_window_boundaries() -> None:
    start = '2026-09-24T10:00:00+08:00'
    end = '2026-10-02T00:00:00+08:00'
    assert (
        preview_cycle_phase(
            start, end, datetime(2026, 9, 24, 1, 59, tzinfo=timezone.utc)
        )
        == 'scheduled'
    )
    assert (
        preview_cycle_phase(start, end, datetime(2026, 9, 24, 2, tzinfo=timezone.utc))
        == 'active'
    )
    assert (
        preview_cycle_phase(start, end, datetime(2026, 10, 1, 16, tzinfo=timezone.utc))
        == 'expired'
    )
