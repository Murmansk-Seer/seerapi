"""Lossless semantic field changes, independent of compact summaries."""

from __future__ import annotations

from typing import Any

PRESENTATION_FIELDS = frozenset(
    {
        'previous_name',
        'previous_payload',
        'previous_description',
        'change_summary',
        'field_changes',
        'field_changes_version',
    }
)


def canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [canonical_value(item) for item in value]
        if _indexed(items) is not None:
            return sorted(items, key=lambda item: str(item['id']))
        return items
    return value


def _indexed(value: list[Any]) -> dict[str, Any] | None:
    if not value or not all(
        isinstance(item, dict)
        and isinstance(item.get('id'), (str, int))
        and not isinstance(item['id'], bool)
        for item in value
    ):
        return None
    result = {str(item['id']): item for item in value}
    return result if len(result) == len(value) else None


def build_field_changes(
    before: dict[str, Any], after: dict[str, Any]
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    def compare(
        path: list[str], old: Any, new: Any, old_exists: bool, new_exists: bool
    ) -> None:
        if old_exists and new_exists:
            if isinstance(old, dict) and isinstance(new, dict):
                for key in sorted(set(old) | set(new)):
                    compare(
                        [*path, str(key)],
                        old.get(key),
                        new.get(key),
                        key in old,
                        key in new,
                    )
                return
            if isinstance(old, list) and isinstance(new, list):
                old_index, new_index = _indexed(old), _indexed(new)
                if (old_index is not None or not old) and (
                    new_index is not None or not new
                ):
                    old_index, new_index = old_index or {}, new_index or {}
                    for key in sorted(set(old_index) | set(new_index)):
                        compare(
                            [*path, f'id={key}'],
                            old_index.get(key),
                            new_index.get(key),
                            key in old_index,
                            key in new_index,
                        )
                    return
            if type(old) is type(new) and old == new:
                return
        change: dict[str, Any] = {
            'path': path,
            'old_exists': old_exists,
            'new_exists': new_exists,
        }
        if old_exists:
            change['old'] = old
        if new_exists:
            change['new'] = new
        changes.append(change)

    compare([], before, after, True, True)
    return changes
