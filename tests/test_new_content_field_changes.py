from dataclasses import replace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from build_new_content_index import _modified_items, _preserve_weekly_origin
from new_content_field_changes import build_field_changes
from new_content_index_models import ContentItem, SourceSnapshotItem


def test_field_changes_keep_missing_null_zero_and_empty_distinct():
    changes = build_field_changes(
        {'removed': None, 'text': '', 'zero': 0, 'items': [], 'nested': {'power': 100}},
        {
            'added': None,
            'text': 'new',
            'zero': None,
            'items': [1],
            'nested': {'power': 120},
        },
    )
    fields = {tuple(item['path']): item for item in changes}
    assert fields[('removed',)] == {
        'path': ['removed'],
        'old_exists': True,
        'new_exists': False,
        'old': None,
    }
    assert fields[('added',)]['old_exists'] is False
    assert 'old' not in fields[('added',)]
    assert fields[('zero',)]['old'] == 0
    assert fields[('text',)]['old'] == ''
    assert fields[('items',)]['old'] == []
    assert fields[('nested', 'power')]['new'] == 120


def test_id_lists_ignore_order_but_track_each_addition_deletion_and_edit():
    before = {'skills': [{'id': 2, 'power': 100}, {'id': 1, 'power': 90}]}
    reordered = {'skills': list(reversed(before['skills']))}
    assert build_field_changes(before, reordered) == []
    changes = build_field_changes(
        before, {'skills': [{'id': 2, 'power': 120}, {'id': 3}]}
    )
    assert [item['path'] for item in changes] == [
        ['skills', 'id=1'],
        ['skills', 'id=2', 'power'],
        ['skills', 'id=3'],
    ]
    assert changes[0]['new_exists'] is False
    assert changes[-1]['old_exists'] is False


def test_full_long_changes_are_not_limited_by_the_compact_summary():
    before = ContentItem('skill', 1, 'old', 1, {'info': '旧' * 500, 'power': 1})
    current = replace(before, name='new', payload={'info': '新' * 500, 'power': 2})
    result = _modified_items(
        (current,), (SourceSnapshotItem.from_content(before),), (before,), {'skill'}
    )
    assert len(result) == 1
    payload = result[0].payload
    assert payload['previous_payload']['info'] == '旧' * 500
    assert (
        next(
            row
            for row in payload['field_changes']
            if row['path'] == ['payload', 'info']
        )['new']
        == '新' * 500
    )
    assert result[0].semantic_digest == current.semantic_digest
    assert (
        _modified_items(
            (current,),
            (SourceSnapshotItem.from_content(result[0]),),
            (result[0],),
            {'skill'},
        )
        == ()
    )


def test_order_and_presentation_metadata_do_not_change_semantic_digest():
    before = ContentItem('pet', 1, 'test', 1, {'skills': [{'id': 1}, {'id': 2}]})
    after = replace(
        before,
        payload={
            'skills': [{'id': 2}, {'id': 1}],
            'previous_payload': {},
            'previous_name': 'old',
            'previous_description': 'old',
            'field_changes': [],
            'field_changes_version': 1,
            'change_summary': ['test'],
        },
    )
    assert before.semantic_digest == after.semantic_digest


def test_origin_stays_fixed_for_all_categories_and_revert_removes_modification():
    before = ContentItem('skill', 1, 'test', 1, {'info': 'base'})
    current = replace(before, payload={'info': 'first'})
    first = _modified_items(
        (current,), (SourceSnapshotItem.from_content(before),), (before,), {'skill'}
    )
    latest = replace(before, payload={'info': 'second'})
    updated = _preserve_weekly_origin(first, first, (latest,))
    assert updated[0].payload['previous_payload'] == {'info': 'base'}
    assert updated[0].payload['field_changes'][0]['old'] == 'base'
    assert updated[0].payload['field_changes'][0]['new'] == 'second'
    assert _preserve_weekly_origin(updated, first, (before,)) == ()


def test_missing_origin_is_not_filled_from_current_values():
    previous = ContentItem(
        'autocard_chip', 1, 'test', 1, {'previous_description': 'old'}, 'modified'
    )
    latest = replace(previous, payload={'description': 'new', 'rarity': 3})
    updated = _preserve_weekly_origin((latest,), (previous,), (latest,))[0]
    assert updated.payload == {
        'description': 'new',
        'rarity': 3,
        'field_changes_version': 0,
    }
