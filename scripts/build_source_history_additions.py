#!/usr/bin/env python3
"""Select source additions from an explicit, checksum-bound generation index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any

SOURCE_DIRECTORIES = ('achievement', 'pet', 'pet_skin', 'skill', 'mintmark', 'suit', 'equip')


def _full_sha(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(f'[0-9a-f]{{{length}}}', value) is not None


def _entries(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(document, dict) or type(document.get('schema_version')) is not int or document['schema_version'] != 1 or not isinstance(document.get('generations'), list):
        raise ValueError('Unsupported source-history index')
    result = {}
    for entry in document['generations']:
        if not isinstance(entry, dict) or not isinstance(entry.get('sources'), dict) or not _full_sha(entry.get('generation_id'), 64) or entry['generation_id'] in result:
            raise ValueError('Invalid or duplicate generation ID')
        if entry.get('base_generation') is not None and (not _full_sha(entry['base_generation'], 64) or entry['base_generation'] not in result):
            raise ValueError('Unknown generation predecessor')
        if type(entry.get('inventory_verified')) is not bool:
            raise ValueError('Generation inventory readiness must be explicit')
        result[entry['generation_id']] = entry
    return result


def _entities(value: Any) -> dict[str, set[int]]:
    if not isinstance(value, dict) or set(value) != set(SOURCE_DIRECTORIES):
        raise ValueError('Generation requires complete source entity categories')
    result = {}
    for category in SOURCE_DIRECTORIES:
        ids = value[category]
        if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
            raise ValueError('Invalid or duplicate generation entity IDs')
        result[category] = set(ids)
    return result


def select_generation(
    document: dict[str, Any], *, generation_id: str = '', source_commit: str = '', sha256: str = ''
) -> dict[str, Any]:
    entries = _entries(document)
    if generation_id:
        if not _full_sha(generation_id, 64):
            raise ValueError('An explicit full generation ID is required')
        matches = [e for identity, e in entries.items() if identity == generation_id]
    else:
        if not _full_sha(source_commit, 40) or not _full_sha(sha256, 64):
            raise ValueError('Legacy selection requires an exact source commit and database digest')
        matches = [e for e in entries.values() if source_commit in e.get('original_revisions', []) and sha256 in e.get('published_sha256', [])]
    if len(matches) != 1:
        raise ValueError('Verified publication does not identify exactly one generation')
    selected = matches[0]
    if selected['inventory_verified'] is not True:
        raise ValueError('Selected generation inventory is not verified')
    additions = selected.get('additions')
    if not isinstance(additions, list):
        raise ValueError('Invalid source-history additions')
    seen = set()
    for item in additions:
        if not isinstance(item, dict) or item.get('category') not in SOURCE_DIRECTORIES or type(item.get('entity_id')) is not int or item['entity_id'] <= 0:
            raise ValueError('Invalid source-history addition')
        pair = (item['category'], item['entity_id'])
        if pair in seen:
            raise ValueError('Duplicate source-history addition')
        seen.add(pair)
    return {key: selected[key] for key in ('generation_id', 'base_generation', 'additions')}


def publication_generation(
    document: dict[str, Any], state: dict[str, Any], *, database_sha256: str, index_revision: str
) -> dict[str, Any]:
    if not _full_sha(database_sha256, 64) or state.get('sha256') != database_sha256:
        raise ValueError('Source-history publication and downloaded database differ')
    if not _full_sha(index_revision, 40) or state.get('source_history_index_revision') != index_revision or state.get('source_commit') != index_revision:
        raise ValueError('Publication must identify the exact immutable generation-index revision')
    identity = state.get('generation_id')
    if not isinstance(identity, str):
        raise ValueError('Publication has no explicit generation ID; await an indexed API rebuild')
    selected = select_generation(document, generation_id=identity)
    entries = _entries(document)
    entry = entries[identity]
    if document.get('latest_generation') != identity or not document['generations'] or document['generations'][-1]['generation_id'] != identity:
        raise ValueError('Publication generation is not latest at its immutable index revision')
    sources = entry.get('sources', {})
    for source_field, state_field in [('config', 'config'), ('patch', 'patch'), ('tooling', 'tooling_revision')]:
        if not _full_sha(state.get(state_field), 40) or sources.get(source_field) != state[state_field]:
            raise ValueError('Publication and generation source bindings differ')
    version = state.get('official_config_version')
    if not isinstance(version, str) or not re.fullmatch('[0-9]{14}', version) or sources.get('official_config_version') != version:
        raise ValueError('Publication and generation official versions differ')
    current = _entities(document.get('latest_entities'))
    previous = _entities(document.get('comparison_base_entities'))
    base = selected['base_generation']
    if document.get('comparison_base_generation') != base or (base is not None and (base not in entries or entries[base]['inventory_verified'] is not True)):
        raise ValueError('Publication comparison generation is not verified')
    expected = {(c, i) for c in SOURCE_DIRECTORIES for i in current[c] - previous[c]}
    if expected != {(a['category'], a['entity_id']) for a in selected['additions']}:
        raise ValueError('Published additions differ from explicit comparison entities')
    canonical = json.dumps({'entities': document['latest_entities'], 'sources': sources}, sort_keys=True, separators=(',', ':'))
    snapshot = hashlib.sha256(canonical.encode()).hexdigest()
    if entry.get('snapshot_id') != snapshot:
        raise ValueError('Published snapshot identity differs from source/entities')
    allowed = {snapshot}
    if len(document['generations']) > 1:
        predecessor = document['generations'][-2]['generation_id']
        allowed.add(hashlib.sha256((snapshot + ':' + predecessor).encode()).hexdigest())
    if identity not in allowed:
        raise ValueError('Published generation ID differs from snapshot/predecessor')
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--publication-state', type=Path, required=True)
    parser.add_argument('--index-revision', required=True)
    parser.add_argument('--database-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    document = json.loads(args.index.read_text(encoding='utf-8'))
    state = json.loads(args.publication_state.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or not isinstance(state, dict):
        raise ValueError('Publication and index must be JSON documents')
    selected = publication_generation(document, state, database_sha256=args.database_sha256, index_revision=args.index_revision)
    args.output.write_bytes((json.dumps(selected, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(f'source-history generation: {selected["generation_id"]}; additions: {len(selected["additions"])}')  # noqa: T201


if __name__ == '__main__':
    main()
