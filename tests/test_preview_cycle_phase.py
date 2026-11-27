"""The scheduler must rebuild even when only the DLL window phase changes."""

from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from preview_cycle_phase import checkpoint_preview_cycle_phase, preview_cycle_phase


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


@pytest.mark.parametrize(('start', 'end'), [('', ''), ('\n', '\n'), (' \n', '\r\n')])
def test_absent_preview_checkpoint_is_explicitly_unavailable(start, end):
    assert (
        checkpoint_preview_cycle_phase(start, end, datetime.now(timezone.utc))
        == 'unavailable'
    )
    with pytest.raises(ValueError, match='Invalid isoformat'):
        preview_cycle_phase(start, end, datetime.now(timezone.utc))


@pytest.mark.parametrize(
    ('start', 'end'),
    [
        ('', '2026-11-27T10:00:00+08:00'),
        ('2026-11-27T10:00:00+08:00', ''),
        ('not a date', 'not a date'),
        ('2026-11-27T10:00:00', '2026-11-28T10:00:00'),
        ('2026-11-28T10:00:00+08:00', '2026-11-27T10:00:00+08:00'),
    ],
)
def test_damaged_preview_checkpoint_still_fails(start, end):
    with pytest.raises(ValueError, match=r'both start|isoformat|timezone|follow start'):
        checkpoint_preview_cycle_phase(start, end, datetime.now(timezone.utc))


def test_checkpoint_classifier_preserves_known_window():
    now = datetime(2026, 11, 27, 4, tzinfo=timezone.utc)
    assert (
        checkpoint_preview_cycle_phase(
            '2026-11-27T10:00:00+08:00\n', '2026-11-28T10:00:00+08:00\n', now
        )
        == 'active'
    )


def test_workflow_uses_checkpoint_semantics_for_read_and_write():
    workflow = (
        Path(__file__).resolve().parents[1]
        / '.github/workflows/build-seerapi-data-db.yml'
    ).read_text('utf-8')
    assert workflow.count('python scripts/preview_cycle_phase.py --checkpoint') == 2
    assert '[ -s .build-state/preview-cycle-start ]' not in workflow
