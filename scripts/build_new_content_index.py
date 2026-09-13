#!/usr/bin/env python3
"""Build the weekly new-content index embedded in the IronsBot data SQLite.

The rolling GitHub release keeps only the latest database.  This script runs
before that release is overwritten, compares the newly-built database with the
previous published one, and embeds the result into the new database.  Runtime
bot instances therefore do not need a local history database.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import json
from pathlib import Path
import sqlite3

from new_content_index_models import (
    CONTENT_CATEGORIES,
    PEAK_POOL_CATEGORIES,
    SEMANTIC_SCHEMA_VERSION,
    CategoryState,
    ContentItem,
    ReleaseState,
    SourceHistoryAddition,
    SourceSnapshotItem,
    semantic_migration_prune_categories,
)
from new_content_index_pool_changes import (
    build_peak_pool_changes,
    merge_weekly_peak_pool_changes,
)
from new_content_index_release import (
    _config_version,
    _load_previous_state,
    _source_categories,
    _weekly_cycle,
    write_release_state,
)
from new_content_index_snapshot import (
    load_current_items,
)


def load_source_history_additions(
    path: Path | None,
) -> tuple[SourceHistoryAddition, ...]:
    """Load Git-confirmed additions without treating source-file edits as changes.

    The API data repository records both real content additions and broad schema
    rewrites. The workflow only writes numeric entities created by Git, so this
    input may safely repair a rolling SQLite baseline that was overwritten after
    an official update became available.
    """
    if path is None or not path.is_file():
        return ()
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        raise ValueError(f'invalid source-history additions: {path}') from error
    raw_additions = document.get('additions', []) if isinstance(document, dict) else []
    if not isinstance(raw_additions, list):
        raise ValueError(f'invalid source-history additions: {path}')
    additions: set[SourceHistoryAddition] = set()
    valid_categories = set(CONTENT_CATEGORIES)
    for raw in raw_additions:
        if not isinstance(raw, dict):
            raise ValueError(f'invalid source-history addition: {raw!r}')
        category = raw.get('category')
        entity_id = raw.get('entity_id')
        if (
            not isinstance(category, str)
            or category not in valid_categories
            or isinstance(entity_id, bool)
            or not isinstance(entity_id, int)
            or entity_id <= 0
        ):
            raise ValueError(f'invalid source-history addition: {raw!r}')
        additions.add(SourceHistoryAddition(category, entity_id))
    return tuple(sorted(additions, key=lambda item: (item.category, item.entity_id)))


def _new_items(
    current: tuple[ContentItem, ...],
    previous: tuple[SourceSnapshotItem, ...],
    comparable_categories: set[str],
) -> tuple[ContentItem, ...]:
    previous_by_id = {(item.category, item.entity_id) for item in previous}
    previous_semantic = {item.semantic_digest for item in previous}
    return tuple(
        item.with_change_kind('added')
        for item in current
        if item.category in comparable_categories
        and item.category not in PEAK_POOL_CATEGORIES
        and (item.category, item.entity_id) not in previous_by_id
        and item.semantic_digest not in previous_semantic
    )


def _modified_items(
    current: tuple[ContentItem, ...],
    previous: tuple[SourceSnapshotItem, ...],
    comparable_categories: set[str],
) -> tuple[ContentItem, ...]:
    previous_by_id = {
        (item.category, item.entity_id): item.semantic_digest for item in previous
    }
    return tuple(
        item.with_change_kind('modified')
        for item in current
        if (previous_item := previous_by_id.get((item.category, item.entity_id)))
        is not None
        and item.category in comparable_categories
        and item.category not in PEAK_POOL_CATEGORIES
        and item.semantic_digest != previous_item
    )


def _source_history_items(
    current: tuple[ContentItem, ...],
    additions: Iterable[SourceHistoryAddition],
) -> tuple[ContentItem, ...]:
    """Resolve Git additions through the current SQLite presentation payload."""
    current_by_id = {(item.category, item.entity_id): item for item in current}
    resolved: list[ContentItem] = []
    for addition in additions:
        categories = (addition.category,)
        if addition.category == 'equip':
            # The source API keeps mounts in the equip collection while the
            # runtime index deliberately presents them as their own category.
            categories = ('equip', 'mount')
        for category in categories:
            if item := current_by_id.get((category, addition.entity_id)):
                resolved.append(item.with_change_kind('added'))
                break
    return tuple(resolved)


def _current_subset(
    candidates: Iterable[ContentItem], current: tuple[ContentItem, ...]
) -> tuple[ContentItem, ...]:
    current_by_id = {(item.category, item.entity_id): item for item in current}
    candidate_by_key = {(item.category, item.entity_id): item for item in candidates}
    return tuple(
        sorted(
            (
                (
                    candidate
                    if candidate.category in PEAK_POOL_CATEGORIES
                    else current_by_id[key].with_change_kind(candidate.change_kind)
                )
                for key, candidate in candidate_by_key.items()
                if key in current_by_id
            ),
            key=lambda item: (item.category, item.entity_id),
        )
    )


def _category_states(
    current_categories: frozenset[str],
    previous_categories: frozenset[str],
) -> tuple[CategoryState, ...]:
    states: list[CategoryState] = []
    for category in CONTENT_CATEGORIES:
        if category not in current_categories:
            states.append(CategoryState(category, False, 'source_unavailable'))
        elif category not in previous_categories:
            states.append(CategoryState(category, False, 'first_observation'))
        else:
            states.append(CategoryState(category, True, 'ready'))
    return tuple(states)


def build_release_state(
    current_path: Path,
    previous_path: Path | None,
    current_git_sha: str,
    source_history_additions: Iterable[SourceHistoryAddition] = (),
) -> ReleaseState:
    with sqlite3.connect(current_path) as conn:
        current_version = _config_version(conn)
        current_items = load_current_items(conn)
        current_categories = _source_categories(conn)
    current_sources = tuple(
        SourceSnapshotItem.from_content(item) for item in current_items
    )
    previous = _load_previous_state(previous_path)
    cycle = _weekly_cycle(current_version)
    if previous is None:
        return ReleaseState(
            current_version,
            current_git_sha,
            cycle,
            False,
            (),
            current_sources,
            current_categories,
            _category_states(current_categories, frozenset()),
        )
    category_states = _category_states(
        current_categories,
        previous.source_categories,
    )
    comparable_categories = {
        state.category for state in category_states if state.comparison_ready
    }
    previous_peak_pool_items: tuple[ContentItem, ...] = ()
    if previous_path is not None and previous_path.is_file():
        with sqlite3.connect(previous_path) as conn:
            previous_peak_pool_items = tuple(
                item
                for item in load_current_items(conn)
                if item.category in PEAK_POOL_CATEGORIES
            )
    increment = _current_subset(
        (
            *_new_items(current_items, previous.source_items, comparable_categories),
            *_modified_items(
                current_items,
                previous.source_items,
                comparable_categories,
            ),
            *build_peak_pool_changes(
                current_items,
                previous_peak_pool_items,
                comparable_categories,
            ),
            *_source_history_items(current_items, source_history_additions),
        ),
        current_items,
    )
    if previous.weekly_cycle == cycle:
        carried_items = previous.items
        if previous.semantic_schema_version < SEMANTIC_SCHEMA_VERSION:
            migration_prune_categories = semantic_migration_prune_categories(
                previous.semantic_schema_version
            )
            carried_items = tuple(
                item
                for item in carried_items
                if not (
                    item.change_kind == 'modified'
                    and item.category in migration_prune_categories
                )
            )
        increment = merge_weekly_peak_pool_changes(carried_items, increment)
        items = _current_subset((*carried_items, *increment), current_items)
        items = tuple(
            item
            for item in items
            if item.category not in PEAK_POOL_CATEGORIES
            or item.payload.get('previous_limit') != item.payload.get('current_limit')
        )
    else:
        items = increment
    return ReleaseState(
        current_version,
        current_git_sha,
        cycle,
        True,
        items,
        current_sources,
        current_categories,
        category_states,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument(
        '--source-history-additions',
        type=Path,
        help='Git-confirmed entity additions from the published API source history.',
    )
    parser.add_argument('--current-git-sha', required=True)
    parser.add_argument(
        '--github-output',
        type=Path,
        help='Optional GitHub Actions output file for release promotion metadata.',
    )
    args = parser.parse_args()

    previous = _load_previous_state(args.previous)
    history_additions = load_source_history_additions(args.source_history_additions)
    state = build_release_state(
        args.current,
        args.previous,
        args.current_git_sha,
        history_additions,
    )
    write_release_state(args.current, state, previous)
    if args.github_output is not None:
        with args.github_output.open('a', encoding='utf-8') as output:
            output.write(f'weekly_cycle={state.weekly_cycle}\n')
            output.write(
                f'baseline_established={str(state.baseline_established).lower()}\n'
            )
    ready_categories = sum(
        1 for category in state.category_states if category.comparison_ready
    )
    status = 'ready' if state.baseline_established else 'history-unavailable'
    print(  # noqa: T201 - CLI status is required by the GitHub Actions log.
        'new-content index: '
        f'status={status} cycle={state.weekly_cycle} '
        f'items={len(state.items)} comparable_categories={ready_categories}'
    )


if __name__ == '__main__':
    main()
