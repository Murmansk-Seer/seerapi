import asyncio
import json

from click.testing import CliRunner
from hishel.httpx import AsyncCacheClient
import httpx
import pytest

from seerapi import SeerAPI, decode_skill_stone_runtime_id
from seerapi.cli import cli_main
from seerapi.cli.context import CliContext


def _skill_payload(skill_id: int) -> dict[str, object]:
    return {
        'id': skill_id,
        'name': '冲撞',
        'power': 35,
        'max_pp': 35,
        'accuracy': 100,
        'crit_rate': 6.25,
        'priority': 0,
        'must_hit': False,
        'atk_num': 1,
        'info': None,
        'category': {
            'id': 1,
            'url': 'https://api.seerapi.com/v1/skill_category/1',
        },
        'type': {
            'id': 1,
            'url': 'https://api.seerapi.com/v1/element_type_combination/1',
        },
        'learned_by_pet': [],
        'skill_effect': [],
        'friend_skill_effect': [],
        'hide_effect': None,
        'advance': None,
    }


def _skill_stone_payload() -> dict[str, object]:
    return {
        'id': 25,
        'name': 'S级电系技能石',
        'move_name': '电石之力-S',
        'rank': 5,
        'power': 160,
        'max_pp': 2,
        'accuracy': 100,
        'category': {
            'id': 5,
            'url': 'https://api.seerapi.com/v1/skill_stone_category/5',
        },
        'item': {
            'id': 1100025,
            'url': 'https://api.seerapi.com/v1/item/1100025',
        },
        'effect': [
            {
                'inner_id': 5,
                'prob': 0.02,
                'effect': [
                    {
                        'info': '技能使用成功时，15%改变自身特防等级+1',
                        'analyze_info': '技能使用成功时，15%改变自身特防等级+1',
                        'args': [3, 15, 1],
                        'effect': {
                            'id': 4,
                            'url': 'https://api.seerapi.com/v1/skill_effect_type/4',
                        },
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    ('skill_id', 'expected'),
    [
        (100070, (1, 0, 70)),
        (200075, (2, 0, 75)),
        (201081, (2, 1, 81)),
        (105025, (1, 5, 25)),
        (202081, (2, 2, 81)),
    ],
)
def test_decode_skill_stone_runtime_id(
    skill_id: int,
    expected: tuple[int, int, int],
) -> None:
    decoded = decode_skill_stone_runtime_id(skill_id)

    assert decoded is not None
    assert (
        decoded.attack_category_id,
        decoded.effect_inner_id,
        decoded.stone_id,
    ) == expected


@pytest.mark.parametrize('skill_id', [0, 100_000, 300_081, 400_000])
def test_decode_skill_stone_runtime_id_rejects_invalid_values(skill_id: int) -> None:
    assert decode_skill_stone_runtime_id(skill_id) is None


def _make_client(handler: httpx.MockTransport) -> SeerAPI:
    client = SeerAPI()
    client._client = AsyncCacheClient(base_url=client.base_url, transport=handler)
    return client


def test_resolve_skill_prefers_a_normal_skill() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, json=_skill_payload(10001))

    async def run() -> None:
        client = _make_client(httpx.MockTransport(handler))
        try:
            resolved = await client.resolve_skill(10001)
        finally:
            await client.aclose()

        assert resolved.kind == 'skill'
        assert resolved.skill is not None
        assert resolved.skill.name == '冲撞'

    asyncio.run(run())
    assert requests == ['/v1/skill/10001']


def test_resolve_skill_fetches_the_selected_skill_stone_effect() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith('/skill/105025'):
            return httpx.Response(404, json={'error': 'Not Found'})
        if request.url.path.endswith('/skill_stone/25'):
            return httpx.Response(200, json=_skill_stone_payload())
        raise AssertionError(f'unexpected request: {request.url}')

    async def run() -> None:
        client = _make_client(httpx.MockTransport(handler))
        try:
            resolved = await client.resolve_skill(105025)
        finally:
            await client.aclose()

        assert resolved.kind == 'skill_stone'
        assert resolved.skill_stone is not None
        assert resolved.skill_stone.move_name == '电石之力-S'
        assert resolved.skill_stone_runtime is not None
        assert resolved.skill_stone_runtime.attack_category_name == '物理'
        assert resolved.skill_stone_runtime.effect_inner_id == 5
        assert resolved.selected_effect is not None
        assert resolved.selected_effect.effect[0].args == [3, 15, 1]

    asyncio.run(run())
    assert requests == ['/v1/skill/105025', '/v1/skill_stone/25']


def test_resolve_skill_rejects_an_unknown_stone_effect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if '/skill/' in request.url.path:
            return httpx.Response(404, json={'error': 'Not Found'})
        return httpx.Response(200, json=_skill_stone_payload())

    async def run() -> None:
        client = _make_client(httpx.MockTransport(handler))
        try:
            with pytest.raises(ValueError, match='has no effect 6'):
                await client.resolve_skill(106025)
        finally:
            await client.aclose()

    asyncio.run(run())


def test_resolve_skill_cli_outputs_structured_runtime_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('/skill/105025'):
            return httpx.Response(404, json={'error': 'Not Found'})
        return httpx.Response(200, json=_skill_stone_payload())

    result = CliRunner().invoke(
        cli_main,
        ['resolve-skill', '105025'],
        obj=CliContext(transport=httpx.MockTransport(handler)),
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload['kind'] == 'skill_stone'
    assert payload['skill_stone_runtime'] == {
        'attack_category_id': 1,
        'attack_category_name': '物理',
        'effect_inner_id': 5,
        'stone_id': 25,
    }
    assert payload['selected_effect']['effect'][0]['args'] == [3, 15, 1]
