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
