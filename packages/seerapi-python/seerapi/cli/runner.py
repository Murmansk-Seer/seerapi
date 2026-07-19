import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar

from seerapi import SeerAPI
from seerapi.cli.context import CliContext

T = TypeVar('T')


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


async def with_client(
    ctx: CliContext,
    func: Callable[[SeerAPI], Awaitable[T]],
) -> T:
    async with ctx.create_client() as client:
        return await func(client)
