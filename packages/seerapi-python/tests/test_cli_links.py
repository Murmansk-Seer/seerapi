from seerapi.cli.links import get_link_rel, parse_link_header


def test_parse_link_header() -> None:
    header = (
        '<https://api.seerapi.com/v1/schemas/error_code>; rel="describedby", '
        '<https://api.seerapi.com/v1/error_code/?offset=20&limit=20>; rel="next"'
    )
    links = parse_link_header(header)
    assert links['describedby'] == 'https://api.seerapi.com/v1/schemas/error_code'
    assert links['next'] == 'https://api.seerapi.com/v1/error_code/?offset=20&limit=20'


def test_get_link_rel() -> None:
    header = '<https://api.seerapi.com/v1/schemas/pet/$id>; rel="describedby"'
    assert get_link_rel(header, 'describedby') == (
        'https://api.seerapi.com/v1/schemas/pet/$id'
    )
    assert get_link_rel(header, 'next') is None
