import asyncio

import httpx
import pytest
from hishel.httpx import AsyncCacheClient

from seerapi import PageInfo, SeerAPI
from seerapi._client import _parse_url_page_info


def test_parse_url_page_info_expand_from_url() -> None:
    page = _parse_url_page_info(
        'https://api.seerapi.com/v1/pet/?offset=10&limit=20&expand=true'
    )
    assert page is not None
    assert page.offset == 10
    assert page.limit == 20
    assert page.expand is True


def test_parse_url_page_info_expand_fallback() -> None:
    page = _parse_url_page_info(
        'https://api.seerapi.com/v1/pet/?offset=10&limit=20',
        expand_fallback=True,
    )
    assert page is not None
    assert page.expand is True


def test_parse_url_page_info_expand_true_when_absent_by_default() -> None:
    page = _parse_url_page_info(
        'https://api.seerapi.com/v1/pet/?offset=0&limit=10',
    )
    assert page is not None
    assert page.expand is True


def test_parse_url_page_info_expand_false_when_absent_with_fallback() -> None:
    page = _parse_url_page_info(
        'https://api.seerapi.com/v1/pet/?offset=0&limit=10',
        expand_fallback=False,
    )
    assert page is not None
    assert page.expand is False


def test_page_info_expand_defaults_to_true() -> None:
    assert PageInfo().expand is True


@pytest.fixture
def error_code_item() -> dict[str, object]:
    return {'id': 1, 'name': 'test_error', 'message': 'test message'}


@pytest.fixture
def list_ref_response(error_code_item: dict[str, object]) -> dict[str, object]:
    return {
        'count': 1,
        'next': None,
        'previous': None,
        'first': 'https://api.seerapi.com/v1/error_code/?offset=0&limit=10',
        'last': None,
        'results': [
            {
                'id': error_code_item['id'],
                'url': f'https://api.seerapi.com/v1/error_code/{error_code_item["id"]}',
                'name': error_code_item['name'],
            }
        ],
    }


def _make_client(handler: httpx.MockTransport) -> SeerAPI:
    client = SeerAPI(hostname='api.seerapi.com', version_path='v1')
    client._client = AsyncCacheClient(
        base_url=client.base_url,
        transport=handler,
    )
    return client


def test_paginated_list_expand_false_uses_n_plus_one(
    error_code_item: dict[str, object],
    list_ref_response: dict[str, object],
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith('/error_code/'):
            assert request.url.params.get('expand') == 'false'
            return httpx.Response(200, json=list_ref_response)
        if request.url.path.endswith('/error_code/1'):
            return httpx.Response(200, json=error_code_item)
        raise AssertionError(f'unexpected request: {request.url}')

    async def run() -> None:
        client = _make_client(httpx.MockTransport(handler))
        response = await client.paginated_list(
            'error_code', PageInfo(offset=0, limit=10, expand=False)
        )
        items = [item async for item in response.results]
        await client.aclose()
        assert len(items) == 1
        assert items[0].name == 'test_error'
        assert len(requests) == 2
        assert requests[0].url.path.endswith('/error_code/')
        assert requests[1].url.path.endswith('/error_code/1')

    asyncio.run(run())


def test_paginated_list_expand_true_skips_item_get(
    error_code_item: dict[str, object],
) -> None:
    requests: list[httpx.Request] = []
    list_response = {
        'count': 1,
        'next': None,
        'previous': None,
        'first': 'https://api.seerapi.com/v1/error_code/?offset=0&limit=10&expand=true',
        'last': None,
        'results': [error_code_item],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path.endswith('/error_code/')
        assert request.url.params.get('expand') == 'true'
        return httpx.Response(200, json=list_response)

    async def run() -> None:
        client = _make_client(httpx.MockTransport(handler))
        response = await client.paginated_list(
            'error_code', PageInfo(offset=0, limit=10)
        )
        items = [item async for item in response.results]
        await client.aclose()
        assert len(items) == 1
        assert items[0].message == 'test message'
        assert len(requests) == 1

    asyncio.run(run())


def test_list_expand_true_propagates_through_pages(
    error_code_item: dict[str, object],
) -> None:
    requests: list[httpx.Request] = []
    page_one = {
        'count': 2,
        'next': 'https://api.seerapi.com/v1/error_code/?offset=1&limit=1',
        'previous': None,
        'first': 'https://api.seerapi.com/v1/error_code/?offset=0&limit=1&expand=true',
        'last': 'https://api.seerapi.com/v1/error_code/?offset=1&limit=1&expand=true',
        'results': [{**error_code_item, 'id': 1}],
    }
    page_two = {
        'count': 2,
        'next': None,
        'previous': 'https://api.seerapi.com/v1/error_code/?offset=0&limit=1&expand=true',
        'first': 'https://api.seerapi.com/v1/error_code/?offset=0&limit=1&expand=true',
        'last': 'https://api.seerapi.com/v1/error_code/?offset=1&limit=1&expand=true',
        'results': [{**error_code_item, 'id': 2, 'name': 'second'}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.params.get('expand') == 'true'
        offset = int(request.url.params['offset'])
        if offset == 0:
            return httpx.Response(200, json=page_one)
        if offset == 1:
            return httpx.Response(200, json=page_two)
        raise AssertionError(f'unexpected offset: {offset}')

    async def run() -> None:
        client = _make_client(httpx.MockTransport(handler))
        names = [item.name async for item in client.list('error_code')]
        await client.aclose()
        assert names == ['test_error', 'second']
        assert len(requests) == 2

    asyncio.run(run())


def test_list_is_async_generator() -> None:
    client = SeerAPI()
    gen = client.list('error_code')
    assert hasattr(gen, '__aiter__')
    asyncio.run(client.aclose())
