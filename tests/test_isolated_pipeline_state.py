from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/build-seerapi-data-db.yml'
ACTION = 'pipeline-state@e50f91b8dc44002ce0e15cad50e88f2bd34d6210'


def test_plan_requires_migrated_state_before_reading_source_fingerprints() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    plan = text.split('  plan:', 1)[1].split('  render-effect-icon-cache:', 1)[0]
    assert (
        plan.index('name: Require migrated pipeline checkpoint')
        < plan.index('name: Restore verified pipeline checkpoint')
        < plan.index('name: Record planned checkpoint revision')
        < plan.index('name: Check data source changes')
    )
    assert 'git ls-remote --exit-code --heads origin refs/heads/pipeline-state' in plan
    assert 'pipeline_state_sha: ${{ steps.pipeline_state_ref.outputs.sha }}' in plan
    assert 'test -n "$state_sha"' in plan


def test_build_restores_exact_plan_state_and_rejects_drift_before_generation() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    build = text.split('  build:', 1)[1].split('  report:', 1)[0]
    assert (
        build.index('name: Restore planned pipeline checkpoint')
        < build.index('name: Verify planned checkpoint is unchanged')
        < build.index('name: Setup Python')
    )
    assert (
        'EXPECTED_PIPELINE_STATE: ${{ needs.plan.outputs.pipeline_state_sha }}' in build
    )
    assert '[ -z "$EXPECTED_PIPELINE_STATE" ]' in build
    assert '[ "$observed" != "$EXPECTED_PIPELINE_STATE" ]' in build
    assert text.count('ref: ${{ needs.plan.outputs.build_sha }}') == 2


def test_only_successfully_verified_release_can_persist_runtime_state() -> None:
    text = WORKFLOW.read_text(encoding='utf-8')
    assert text.count(ACTION) == 3
    assert 'git add .build-state' not in text
    assert 'python scripts/push_build_state.py' not in text
    assert (
        text.index('id: verify_release')
        < text.index('name: Record data source checksums')
        < text.index('name: Persist verified publication checkpoint')
    )
    persist = text.split('name: Persist verified publication checkpoint', 1)[1]
    assert "if: steps.verify_release.outcome == 'success'" in persist
    assert 'mode: publish' in persist


def test_ignored_runtime_state_is_absent_from_source_index() -> None:
    assert '/.build-state/' in (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert (
        subprocess.check_output(['git', 'ls-files', '--', '.build-state'], cwd=ROOT)
        == b''
    )
