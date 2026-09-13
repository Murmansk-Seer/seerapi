"""Compare and accumulate weekly peak-pool position changes."""

from __future__ import annotations

from dataclasses import replace

from new_content_index_models import PEAK_POOL_CATEGORIES, ContentItem


def build_peak_pool_changes(
    current: tuple[ContentItem, ...],
    previous: tuple[ContentItem, ...],
    comparable_categories: set[str],
) -> tuple[ContentItem, ...]:
    comparable = PEAK_POOL_CATEGORIES.intersection(comparable_categories)
    previous_by_key = {
        (item.category, item.entity_id): item
        for item in previous
        if item.category in comparable
    }
    changes: list[ContentItem] = []
    for item in current:
        if item.category not in comparable:
            continue
        previous_item = previous_by_key.get((item.category, item.entity_id))
        if previous_item is None:
            continue
        previous_limit = previous_item.payload.get('limit')
        current_limit = item.payload.get('limit')
        if previous_limit == current_limit:
            continue
        changes.append(
            replace(
                item,
                payload={
                    'previous_limit': previous_limit,
                    'current_limit': current_limit,
                },
                change_kind='modified',
            )
        )
    return tuple(changes)


def merge_weekly_peak_pool_changes(
    carried: tuple[ContentItem, ...],
    increment: tuple[ContentItem, ...],
) -> tuple[ContentItem, ...]:
    """Keep the week's original position while accepting the latest position."""

    carried_by_key = {
        (item.category, item.entity_id): item
        for item in carried
        if item.category in PEAK_POOL_CATEGORIES
    }
    merged: list[ContentItem] = []
    for item in increment:
        if item.category not in PEAK_POOL_CATEGORIES:
            merged.append(item)
            continue
        previous = carried_by_key.get((item.category, item.entity_id))
        if previous is None:
            merged.append(item)
            continue
        combined = replace(
            item,
            payload={
                'previous_limit': previous.payload.get('previous_limit'),
                'current_limit': item.payload.get('current_limit'),
            },
        )
        # Keep a reverted transition until it replaces the carried row; the
        # final equality filter then removes it from the release.
        merged.append(combined)
    return tuple(merged)
