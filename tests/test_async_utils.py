# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0

import asyncio
from time import monotonic

from orggatekeeper.async_utils import gather_with_concurrency


async def test_gather_with_concurrency() -> None:
    """Test gather with concurrency."""
    start = monotonic()
    await asyncio.gather(
        *[
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
        ]
    )
    end = monotonic()
    duration = end - start
    assert duration < 0.15

    start = monotonic()
    await gather_with_concurrency(
        3,
        *[
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
        ],
    )
    end = monotonic()
    duration = end - start
    assert duration < 0.15

    start = monotonic()
    await gather_with_concurrency(
        1,
        *[
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
            asyncio.sleep(0.1),
        ],
    )
    end = monotonic()
    duration = end - start
    assert duration > 0.3
