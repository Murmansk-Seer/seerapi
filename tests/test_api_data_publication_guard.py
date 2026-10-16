from scripts.check_api_data_publication import publication_matches


def test_current_source_requires_matching_release_digest() -> None:
    state = {'config': 'new-source', 'sha256': 'new-digest'}
    assert publication_matches(state, 'new-source', 'new-digest')
    assert not publication_matches(state, 'older-source', 'new-digest')
    assert not publication_matches(state, 'new-source', 'older-digest')
    assert not publication_matches({}, 'new-source', 'new-digest')
