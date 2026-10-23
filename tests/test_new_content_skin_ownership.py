from dataclasses import replace
import json
from pathlib import Path
import sqlite3

import pytest
from test_build_new_content_index import _create_database, indexer


@pytest.mark.parametrize('category', ['pet', 'autocard_card'])
def test_skin_association_does_not_modify_owner(category: str) -> None:
    before = indexer.ContentItem(category, 6, 'owner', 6, {'attack': 2})
    after = replace(before, payload={'attack': 2, 'skins': '0,50016'})
    assert before.semantic_digest == after.semantic_digest
    assert after.payload['skins'] == '0,50016'
    assert (
        indexer._modified_items(
            (after,),
            (indexer.SourceSnapshotItem.from_content(before),),
            (before,),
            {category},
        )
        == ()
    )
    # A genuinely new owner still counts, even when it already has skins.
    assert indexer._new_items((after,), (), {category}) == (
        after.with_change_kind('added'),
    )


@pytest.mark.parametrize('category', ['pet', 'autocard_card'])
def test_real_change_with_new_skin_remains_visible(category: str) -> None:
    before = indexer.ContentItem(category, 6, 'owner', 6, {'attack': 2})
    after = replace(before, payload={'attack': 3, 'skins': '0,50016'})
    (change,) = indexer._modified_items(
        (after,),
        (indexer.SourceSnapshotItem.from_content(before),),
        (before,),
        {category},
    )
    assert change.change_kind == 'modified'
    assert change.payload['change_summary'] == ['attack：2 → 3']
    assert all('skins' not in item['path'] for item in change.payload['field_changes'])


def test_weekly_rebuild_discards_skin_only_change_and_normalizes_old_origin() -> None:
    before = indexer.ContentItem(
        'autocard_card', 6, 'owner', 6, {'attack': 2, 'skins': ''}
    )
    after = replace(before, payload={'attack': 2, 'skins': '0,50016'})
    carried = replace(
        after,
        change_kind='modified',
        payload={
            **after.payload,
            'previous_name': before.name,
            'previous_payload': before.payload,
        },
    )
    assert indexer._preserve_weekly_origin((carried,), (carried,), (after,)) == ()
    after = replace(after, payload={**after.payload, 'attack': 3})
    (change,) = indexer._preserve_weekly_origin((carried,), (carried,), (after,))
    assert change.payload['previous_payload'] == {'attack': 2}
    assert all('skins' not in item['path'] for item in change.payload['field_changes'])


def test_release_counts_new_skin_but_not_its_existing_owner(tmp_path: Path) -> None:
    previous, current = tmp_path / 'previous.sqlite', tmp_path / 'current.sqlite'
    for path, version, skins in (
        (previous, '20261016152146', ''),
        (current, '20261023142631', '0,50016'),
    ):
        _create_database(path, version=version, pet_ids=(1,))
        with sqlite3.connect(path) as conn:
            conn.execute(
                'CREATE TABLE autocard_card(id INTEGER, name TEXT, raw_json TEXT)'
            )
            conn.execute(
                'INSERT INTO autocard_card VALUES (6,?,?)',
                (
                    'owner',
                    json.dumps({'attack': 2, 'skins': skins}),
                ),
            )
    with sqlite3.connect(current) as conn:
        conn.execute("INSERT INTO pet_skin VALUES (101, 'new skin', 101, 1)")
    state = indexer.build_release_state(current, previous, 'skin-test')
    assert {(item.category, item.entity_id) for item in state.items} == {
        ('pet_skin', 101)
    }


def test_migration_rehashes_skin_links_in_previous_snapshot(tmp_path: Path) -> None:
    previous, current = tmp_path / 'previous.sqlite', tmp_path / 'current.sqlite'
    for path in (previous, current):
        _create_database(path, version='20261023142631', pet_ids=(1,))
        with sqlite3.connect(path) as conn:
            conn.execute(
                'CREATE TABLE autocard_card(id INTEGER, name TEXT, raw_json TEXT)'
            )
            conn.execute(
                'INSERT INTO autocard_card VALUES (6,?,?)',
                ('owner', '{"attack":2,"skins":"0,50016"}'),
            )
    state = indexer.build_release_state(previous, None, 'previous')
    indexer.write_release_state(previous, state, None)
    with sqlite3.connect(previous) as conn:
        conn.execute('UPDATE new_content_release SET schema_version=7')
        conn.execute(
            "UPDATE new_content_source_snapshot SET semantic_digest='old-digest' WHERE category='autocard_card'"
        )
    assert indexer.build_release_state(current, previous, 'rehash').items == ()
