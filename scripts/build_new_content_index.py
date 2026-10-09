#!/usr/bin/env python3
"""Build the weekly new-content index embedded in the SeerAPI data SQLite.

The rolling GitHub release keeps only the latest database.  This script runs
before that release is overwritten, compares the newly-built database with the
previous published one, and embeds the result into the new database.  Runtime
bot instances therefore do not need a local history database.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from new_content_index_models import (
    AUTOCARD_CHIP_CATEGORY,
    CONTENT_CATEGORIES,
    PEAK_POOL_CATEGORIES,
    SEMANTIC_SCHEMA_VERSION,
    CategoryState,
    ContentItem,
    ReleaseState,
    SourceHistoryAddition,
    SourceSnapshotItem,
    semantic_migration_prune_categories,
    semantic_migration_suppress_modified_categories,
)
from new_content_index_pool_changes import (
    build_peak_pool_changes,
    merge_weekly_peak_pool_changes,
)
from new_content_index_release import (
    _config_version,
    _load_previous_state,
    _source_categories,
    _source_cycle_date,
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


_CHANGE_FIELD_LABELS = {
    'accuracy': '命中',
    'advance_id': '进阶效果',
    'bonus': '效果',
    'category_id': '分类',
    'crit_rate': '暴击率',
    'desc': '效果说明',
    'description': '效果说明',
    'info': '技能说明',
    'learning_level': '学习等级',
    'max_pp': 'PP',
    'must_hit': '必中',
    'power': '威力',
    'priority': '先制',
    'quality': '品质',
    'suit_desc': '套装说明',
    'transform': '变身效果',
    'type_id': '属性',
}
_STAT_FIELD_LABELS = {
    'atk': '攻击',
    'def': '防御',
    'def_': '防御',
    'hp': '体力',
    'sp_atk': '特攻',
    'sp_def': '特防',
    'spd': '速度',
}
_CHANGE_SUMMARY_LIMIT = 4


def _format_change(label: str, previous: object, current: object) -> str:
    if isinstance(previous, (dict, list)) or isinstance(current, (dict, list)):
        return f'{label}已更新'
    if isinstance(previous, str) or isinstance(current, str):
        previous_text = str(previous or '').strip()
        current_text = str(current or '').strip()
        if max(len(previous_text), len(current_text)) > 32:
            return f'{label}已更新'
        return f'{label}：{previous_text or "无"} → {current_text or "无"}'
    return f'{label}：{previous} → {current}'


def _content_change_summary(previous: ContentItem, current: ContentItem) -> list[str]:
    summary: list[str] = []
    if previous.name != current.name:
        summary.append(f'名称：{previous.name} → {current.name}')
    old_payload = previous.semantic_payload
    new_payload = current.semantic_payload
    for key in sorted(set(old_payload) | set(new_payload)):
        old_value = old_payload.get(key)
        new_value = new_payload.get(key)
        if old_value == new_value:
            continue
        if (
            key == 'stats'
            and isinstance(old_value, dict)
            and isinstance(new_value, dict)
        ):
            for stat in sorted(set(old_value) | set(new_value)):
                if old_value.get(stat) != new_value.get(stat):
                    summary.append(
                        _format_change(
                            str(_STAT_FIELD_LABELS.get(stat, stat)),
                            old_value.get(stat),
                            new_value.get(stat),
                        )
                    )
            continue
        summary.append(
            _format_change(
                str(_CHANGE_FIELD_LABELS.get(key, key)), old_value, new_value
            )
        )
    if len(summary) <= _CHANGE_SUMMARY_LIMIT:
        return summary
    return [
        *summary[:_CHANGE_SUMMARY_LIMIT],
        f'另有 {len(summary) - _CHANGE_SUMMARY_LIMIT} 项数据更新',
    ]


def _modified_items(
    current: tuple[ContentItem, ...],
    previous: tuple[SourceSnapshotItem, ...],
    previous_raw_items: tuple[ContentItem, ...],
    comparable_categories: set[str],
) -> tuple[ContentItem, ...]:
    previous_by_id = {
        (item.category, item.entity_id): item.semantic_digest for item in previous
    }
    previous_raw_by_id = {
        (item.category, item.entity_id): item for item in previous_raw_items
    }
    return tuple(
        replace(
            item,
            payload={
                **item.payload,
                **(
                    {
                        'previous_name': previous_raw_by_id[
                            (item.category, item.entity_id)
                        ].name,
                        'previous_payload': previous_raw_by_id[
                            (item.category, item.entity_id)
                        ].semantic_payload,
                        'previous_description': str(
                            previous_raw_by_id[(item.category, item.entity_id)]
                            .payload.get('description', '')
                        )
                    }
                    if item.category == AUTOCARD_CHIP_CATEGORY else {}
                ),
                'change_summary': _content_change_summary(
                    previous_raw_by_id[(item.category, item.entity_id)], item
                ),
            },
            change_kind='modified',
        )
        for item in current
        if (previous_item := previous_by_id.get((item.category, item.entity_id)))
        is not None
        and (item.category, item.entity_id) in previous_raw_by_id
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
    candidate_by_key: dict[tuple[str, int], ContentItem] = {}
    for item in candidates:
        key = (item.category, item.entity_id)
        existing = candidate_by_key.get(key)
        if existing is None or existing.change_kind != 'added':
            candidate_by_key[key] = item
        elif item.change_kind == 'added':
            candidate_by_key[key] = item
    return tuple(
        sorted(
            (
                (
                    replace(
                        (
                            candidate
                            if (
                                candidate.category in PEAK_POOL_CATEGORIES
                                or candidate.change_kind == 'modified'
                            )
                            else current_by_id[key]
                        ),
                        change_kind=candidate.change_kind,
                    )
                )
                for key, candidate in candidate_by_key.items()
                if key in current_by_id
            ),
            key=lambda item: (item.category, item.entity_id),
        )
    )


def _preserve_weekly_chip_origin(
    items: tuple[ContentItem, ...],
    carried: tuple[ContentItem, ...],
    current: tuple[ContentItem, ...],
) -> tuple[ContentItem, ...]:
    previous_by_id = {
        item.entity_id: item
        for item in carried
        if item.category == AUTOCARD_CHIP_CATEGORY and item.change_kind == 'modified'
    }
    current_by_id = {
        item.entity_id: item
        for item in current
        if item.category == AUTOCARD_CHIP_CATEGORY
    }
    result: list[ContentItem] = []
    for item in items:
        if item.category != AUTOCARD_CHIP_CATEGORY or item.change_kind != 'modified':
            result.append(item)
            continue
        current_item = current_by_id.get(item.entity_id)
        if current_item is None:
            continue
        carried_item = previous_by_id.get(item.entity_id)
        origin = carried_item or item
        previous_payload = origin.payload.get('previous_payload')
        if not isinstance(previous_payload, dict):
            previous_payload = {
                **current_item.semantic_payload,
                'description': str(origin.payload.get('previous_description', '')),
            }
        previous_name = str(origin.payload.get('previous_name', current_item.name))
        previous_item = ContentItem(
            AUTOCARD_CHIP_CATEGORY,
            item.entity_id,
            previous_name,
            current_item.sort_value,
            previous_payload,
        )
        if previous_item.semantic_key == current_item.semantic_key:
            continue
        result.append(replace(item, payload={
            **current_item.payload,
            'previous_name': previous_name,
            'previous_payload': previous_payload,
            'previous_description': str(previous_payload.get('description', '')),
            'change_summary': _content_change_summary(previous_item, current_item),
        }))
    return tuple(result)


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


def _source_has_reached_cycle(source_version: str, cycle_start: str) -> bool:
    """Do not call an empty cycle complete while the official data is still old."""
    if len(source_version) != 14 or not source_version.isdigit():
        return False
    try:
        published_at = datetime.strptime(source_version, '%Y%m%d%H%M%S')
    except ValueError:
        return False
    published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at >= datetime.fromisoformat(cycle_start)


def build_release_state(
    current_path: Path,
    previous_path: Path | None,
    current_git_sha: str,
    source_history_additions: Iterable[SourceHistoryAddition] = (),
    *,
    cycle_start: str | None = None,
    baseline_path: Path | None = None,
) -> ReleaseState:
    with sqlite3.connect(current_path) as conn:
        current_version = _config_version(conn)
        current_items = load_current_items(conn)
        current_categories = _source_categories(conn)
    current_sources = tuple(
        SourceSnapshotItem.from_content(item) for item in current_items
    )
    previous = _load_previous_state(baseline_path if cycle_start else previous_path)
    cycle = cycle_start or _source_cycle_date(current_version)
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
    modified_items = _modified_items(
        current_items,
        previous.source_items,
        previous.raw_items,
        comparable_categories,
    )
    if (
        previous.baseline_established
        and previous.semantic_schema_version < SEMANTIC_SCHEMA_VERSION
    ):
        suppressed = semantic_migration_suppress_modified_categories(
            previous.semantic_schema_version
        )
        modified_items = tuple(
            item for item in modified_items if item.category not in suppressed
        )
    history_items = _source_history_items(current_items, source_history_additions)
    if cycle_start is not None:
        baseline_keys = {
            (item.category, item.entity_id) for item in previous.source_items
        }
        history_items = tuple(
            item for item in history_items
            if (item.category, item.entity_id) not in baseline_keys
        )
    increment = _current_subset(
        (
            *_new_items(current_items, previous.source_items, comparable_categories),
            *modified_items,
            *build_peak_pool_changes(
                current_items,
                previous.raw_items,
                comparable_categories,
            ),
            *history_items,
        ),
        current_items,
    )
    if cycle_start is None and previous.weekly_cycle == cycle:
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
        items = _preserve_weekly_chip_origin(items, carried_items, current_items)
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
    parser.add_argument('--cycle-start', default='')
    parser.add_argument('--cycle-end', default='')
    parser.add_argument('--preview-manifest-version', default='')
    parser.add_argument('--preview-dll-hash', default='')
    parser.add_argument('--preview-ui-hash', default='')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--maintenance-mode', action='store_true')
    parser.add_argument('--maintenance-start', default='')
    parser.add_argument('--maintenance-end', default='')
    parser.add_argument('--maintenance-source', default='')
    parser.add_argument('--maintenance-notice-id', default='')
    parser.add_argument(
        '--github-output',
        type=Path,
        help='Optional GitHub Actions output file for release promotion metadata.',
    )
    args = parser.parse_args()
    if args.maintenance_start:
        boundary = datetime.fromisoformat(args.maintenance_start)
        if boundary.tzinfo is None:
            parser.error('maintenance start requires a timezone')
        if args.baseline is None:
            parser.error('maintenance indexing requires a verified fixed baseline')

    if bool(args.cycle_start) != bool(args.cycle_end):
        parser.error('both --cycle-start and --cycle-end are required')
    if args.cycle_start:
        start = datetime.fromisoformat(args.cycle_start)
        end = datetime.fromisoformat(args.cycle_end)
        if start.tzinfo is None or end.tzinfo is None or not start < end:
            parser.error('preview cycle requires ordered timezone-aware dates')

    previous = _load_previous_state(args.previous)
    baseline = _load_previous_state(args.baseline) if args.maintenance_mode else previous
    history_additions = load_source_history_additions(args.source_history_additions)
    state = build_release_state(
        args.current,
        args.previous,
        args.current_git_sha,
        history_additions,
        cycle_start=(args.maintenance_start if args.maintenance_mode else args.cycle_start) or None,
        baseline_path=args.baseline,
    )
    status = 'ready'
    if args.maintenance_mode:
        now = datetime.now(timezone.utc)
        if not args.maintenance_start:
            status = 'cycle_unavailable'
        elif now < datetime.fromisoformat(args.maintenance_start):
            status = 'scheduled'
        elif not state.baseline_established:
            status = 'baseline_unavailable'
        elif state.items or (baseline is not None and state.config_version != baseline.config_version):
            status = 'ready'
        else:
            status = 'syncing'
        if status != 'ready':
            state = replace(state, items=())
    elif args.cycle_start:
        now = datetime.now().astimezone()
        start = datetime.fromisoformat(args.cycle_start)
        end = datetime.fromisoformat(args.cycle_end)
        status = (
            'expired' if now >= end else
            'scheduled' if now < start else
            'baseline_unavailable' if not state.baseline_established else
            'ready' if state.items or _source_has_reached_cycle(
                state.config_version, args.cycle_start
            ) else 'syncing'
        )
        if status != 'ready':
            state = replace(state, items=())
    write_release_state(args.current, state, previous)
    if args.maintenance_mode:
        with sqlite3.connect(args.current) as conn:
            conn.executemany(
                'INSERT OR REPLACE INTO seerapi_metadata (key, value) VALUES (?, ?)',
                (
                    ('update_cycle_start', args.maintenance_start),
                    ('update_cycle_end', args.maintenance_end),
                    ('update_cycle_source', args.maintenance_source),
                    ('update_cycle_notice_id', args.maintenance_notice_id),
                    ('update_cycle_status', status),
                ),
            )
    if args.cycle_start:
        with sqlite3.connect(args.current) as conn:
            conn.executemany(
                'INSERT OR REPLACE INTO seerapi_metadata (key, value) VALUES (?, ?)',
                (
                    ('preview_cycle_start', args.cycle_start),
                    ('preview_cycle_end', args.cycle_end),
                    ('preview_manifest_version', args.preview_manifest_version),
                    ('preview_dll_hash', args.preview_dll_hash),
                    ('preview_ui_hash', args.preview_ui_hash),
                    ('new_content_cycle_status', status),
                ),
            )
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
