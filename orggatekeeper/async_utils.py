# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

from asyncio import Semaphore
from asyncio import gather
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


async def gather_with_concurrency(parallel: int, *tasks: Awaitable[T]) -> list[T]:
    """Asyncio gather, but with limited concurrency.

    Args:
        parallel: The number of concurrent tasks being executed.
        tasks: List of tasks to execute.

    Returns:
        List of return values from awaiting the tasks.
    """
    semaphore = Semaphore(parallel)

    async def semaphore_task(task: Awaitable[T]) -> T:
        async with semaphore:
            return await task

    return await gather(*map(semaphore_task, tasks))
