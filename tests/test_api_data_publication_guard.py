from unittest.mock import patch

import pytest

from scripts.check_api_data_publication import (
    publication_matches,
    verified_publication_matches,
)


def test_current_source_requires_matching_release_digest() -> None:
    state = {'config': 'new-source', 'sha256': 'new-digest'}
    assert publication_matches(state, 'new-source', 'new-digest')
    assert not publication_matches(state, 'older-source', 'new-digest')
    assert not publication_matches(state, 'new-source', 'older-digest')
    assert not publication_matches({}, 'new-source', 'new-digest')


def test_identical_trees_accept_history_merge_but_not_wrong_digest() -> None:
    state = {'config': 'published', 'sha256': 'digest'}
    assert publication_matches(
        state, 'merged', 'digest', source_tree='tree', published_tree='tree'
    )
    assert not publication_matches(
        state, 'merged', 'wrong', source_tree='tree', published_tree='tree'
    )


@pytest.mark.parametrize(
    ('current', 'published'), [('', ''), ('tree', ''), ('', 'tree'), ('new', 'old')]
)
def test_missing_or_different_tree_is_blocked(current: str, published: str) -> None:
    assert not publication_matches(
        {'config': 'old', 'sha256': 'digest'},
        'new',
        'digest',
        source_tree=current,
        published_tree=published,
    )


def test_tree_lookup_uses_immutable_published_commit() -> None:
    current = {'sha': 'merged', 'commit': {'tree': {'sha': 'tree'}}}
    published = {'sha': 'original', 'commit': {'tree': {'sha': 'tree'}}}
    state = {'config': 'original', 'sha256': 'digest'}
    with patch(
        'scripts.check_api_data_publication.get_json', return_value=published
    ) as get:
        assert verified_publication_matches(state, current, 'digest')
        get.assert_called_once_with('config-sources/commits/original')


@pytest.mark.parametrize('published', [None, {}, {'sha': 'wrong'}, {'sha': 'original'}])
def test_unavailable_or_incomplete_publication_fails_closed(
    published: dict | None,
) -> None:
    with patch('scripts.check_api_data_publication.get_json', return_value=published):
        assert not verified_publication_matches(
            {'config': 'original', 'sha256': 'digest'},
            {'sha': 'merged', 'commit': {'tree': {'sha': 'tree'}}},
            'digest',
        )


def test_digest_mismatch_never_bypasses_check_or_queries_trees() -> None:
    with patch('scripts.check_api_data_publication.get_json') as get:
        assert not verified_publication_matches(
            {'config': 'original', 'sha256': 'digest'},
            {'sha': 'merged'},
            'wrong',
        )
        get.assert_not_called()


def test_lookup_error_is_not_swallowed() -> None:
    with patch(
        'scripts.check_api_data_publication.get_json',
        side_effect=RuntimeError('network'),
    ):
        with pytest.raises(RuntimeError, match='network'):
            verified_publication_matches(
                {'config': 'original', 'sha256': 'digest'},
                {'sha': 'merged'},
                'digest',
            )
