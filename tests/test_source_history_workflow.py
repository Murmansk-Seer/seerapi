from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / '.github'
    / 'workflows'
    / 'build-seerapi-data-db.yml'
)


def test_source_history_uses_checksum_bound_explicit_generation() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')
    assert 'publication.json?ref=pipeline-state' in workflow
    assert '--index-revision "$index_revision" --database-sha256 "$EXPECTED_API_DATA_SHA"' in workflow
    assert '${index_revision}/data/v1/source-history-index.json' in workflow
    assert '--before=' not in workflow
    assert 'asset_updated_at' not in workflow
    assert "--grep='^Auto update config '" not in workflow
    assert 'args=(--current seerapi-data.sqlite --current-git-sha "${{ needs.plan.outputs.build_sha }}")' in workflow


def test_manual_weekly_index_rebuild_uses_prior_cycle_baseline() -> None:
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert 'rebuild_weekly_index:' in workflow
    assert 'scripts/maintenance_baseline.py' in workflow
    assert 'needs.plan.outputs.maintenance_start' in workflow
    assert '--maintenance-mode' in workflow
    assert 'datetime.strptime(match.group(1)' not in workflow
