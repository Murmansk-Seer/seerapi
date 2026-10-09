from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / '.github'
    / 'workflows'
    / 'build-seerapi-data-db.yml'
)


def test_source_history_uses_previous_fork_generation_as_baseline() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'git -C "${history_dir}" log --first-parent -1' in workflow
    assert '--format=%H --grep=\'^Auto update config \' "${source_head}^"' in workflow


def test_manual_weekly_index_rebuild_uses_prior_cycle_baseline() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'rebuild_weekly_index:' in workflow
    assert 'scripts/maintenance_baseline.py' in workflow
    assert 'needs.plan.outputs.maintenance_start' in workflow
    assert '--maintenance-mode' in workflow
    assert 'datetime.strptime(match.group(1)' not in workflow
