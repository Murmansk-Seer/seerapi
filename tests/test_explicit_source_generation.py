from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from build_new_content_index import load_source_history_additions
import build_source_history_additions as history
import pytest


def fixture_documents() -> tuple[dict, dict]:
    entities = {c: [] for c in history.SOURCE_DIRECTORIES}
    previous = copy.deepcopy(entities)
    entities['pet'] = [13311]
    sources = {'config': '1' * 40, 'patch': '2' * 40, 'tooling': '3' * 40, 'official_config_version': '20261106181039'}
    snapshot = hashlib.sha256(json.dumps({'entities': entities, 'sources': sources}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    base = {'generation_id': 'a' * 64, 'base_generation': None, 'inventory_verified': True, 'sources': {}, 'additions': []}
    current = {'generation_id': snapshot, 'snapshot_id': snapshot, 'base_generation': base['generation_id'], 'inventory_verified': True, 'sources': sources, 'additions': [{'category': 'pet', 'entity_id': 13311}]}
    document = {'schema_version': 1, 'generations': [base, current], 'latest_generation': snapshot, 'latest_entities': entities, 'comparison_base_entities': previous, 'comparison_base_generation': base['generation_id']}
    state = {'generation_id': snapshot, 'source_commit': '4' * 40, 'source_history_index_revision': '4' * 40, 'config': sources['config'], 'patch': sources['patch'], 'tooling_revision': sources['tooling'], 'official_config_version': sources['official_config_version'], 'sha256': 'd' * 64}
    return document, state


def test_exact_source_and_database_select_without_dates() -> None:
    document, state = fixture_documents()
    selected = history.publication_generation(document, state, database_sha256='d' * 64, index_revision='4' * 40)
    assert selected == {k: document['generations'][-1][k] for k in ('generation_id', 'base_generation', 'additions')}


@pytest.mark.parametrize('field', ['config', 'patch', 'tooling_revision', 'official_config_version', 'source_commit', 'source_history_index_revision', 'sha256'])
def test_wrong_receipt_binding_is_rejected(field: str) -> None:
    document, state = fixture_documents()
    state[field] = 'wrong'
    message = {'config': 'source bindings differ', 'patch': 'source bindings differ', 'tooling_revision': 'source bindings differ', 'official_config_version': 'official versions differ', 'source_commit': 'immutable generation-index revision', 'source_history_index_revision': 'immutable generation-index revision', 'sha256': 'downloaded database differ'}[field]
    with pytest.raises(ValueError, match=message):
        history.publication_generation(document, state, database_sha256='d' * 64, index_revision='4' * 40)


@pytest.mark.parametrize('kind', ['duplicate', 'unknown', 'unready', 'additions', 'entities', 'snapshot', 'identity', 'predecessor'])
def test_corrupt_or_unready_index_cannot_supply_additions(kind: str) -> None:
    document, state = fixture_documents()
    entry = document['generations'][-1]
    if kind == 'duplicate':
        document['generations'].append(copy.deepcopy(entry))
    elif kind == 'unknown':
        state['generation_id'] = '0' * 64
    elif kind == 'unready':
        entry['inventory_verified'] = False
    elif kind == 'additions':
        entry['additions'].append({'category': 'pet', 'entity_id': 13311})
    elif kind == 'entities':
        document['latest_entities']['pet'].append(1)
    elif kind == 'snapshot':
        entry['snapshot_id'] = '0' * 64
    elif kind == 'identity':
        entry['generation_id'] = '0' * 64
        document['latest_generation'] = '0' * 64
        state['generation_id'] = '0' * 64
    else:
        entry['base_generation'] = '0' * 64
    message = {'duplicate': 'duplicate generation ID', 'unknown': 'exactly one generation', 'unready': 'not verified', 'additions': 'Duplicate source-history addition', 'entities': 'additions differ', 'snapshot': 'snapshot identity differs', 'identity': 'generation ID differs', 'predecessor': 'Unknown generation predecessor'}[kind]
    with pytest.raises(ValueError, match=message):
        history.publication_generation(document, state, database_sha256='d' * 64, index_revision='4' * 40)


def test_legacy_manual_selection_requires_exact_source_and_digest() -> None:
    document, _ = fixture_documents()
    entry = document['generations'][0]
    entry['original_revisions'] = ['5' * 40]
    entry['published_sha256'] = ['6' * 64]
    assert history.select_generation(document, source_commit='5' * 40, sha256='6' * 64)['generation_id'] == 'a' * 64
    with pytest.raises(ValueError, match='exact source commit and database digest'):
        history.select_generation(document, source_commit='5' * 40)
    entry['inventory_verified'] = False
    with pytest.raises(ValueError, match='not verified'):
        history.select_generation(document, source_commit='5' * 40, sha256='6' * 64)


def test_cli_failure_keeps_existing_validated_output(tmp_path: Path) -> None:
    document, state = fixture_documents()
    state['sha256'] = '0' * 64
    index, receipt, output = (tmp_path / name for name in ('index.json', 'receipt.json', 'additions.json'))
    index.write_text(json.dumps(document), encoding='utf-8')
    receipt.write_text(json.dumps(state), encoding='utf-8')
    output.write_bytes(b'previous validated output')
    result = subprocess.run([sys.executable, str(Path(history.__file__)), '--index', str(index), '--publication-state', str(receipt), '--index-revision', '4' * 40, '--database-sha256', 'd' * 64, '--output', str(output)], capture_output=True, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == b'previous validated output'


def test_explicit_missing_or_malformed_addition_document_fails(tmp_path: Path) -> None:
    assert load_source_history_additions(None) == ()
    path = tmp_path / 'additions.json'
    with pytest.raises(ValueError, match='missing source-history'):
        load_source_history_additions(path)
    for value in ([], {}, {'additions': None}):
        path.write_text(json.dumps(value), encoding='utf-8')
        with pytest.raises(ValueError, match='invalid source-history'):
            load_source_history_additions(path)
