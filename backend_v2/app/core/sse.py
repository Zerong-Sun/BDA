from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .metrics import SSE_STREAM_OUTCOMES


async def observed_sse[T](name: str, source: AsyncIterator[T]) -> AsyncIterator[T]:
    """Record terminal SSE outcomes without retaining request database sessions."""
    try:
        async for item in source:
            yield item
    except asyncio.CancelledError:
        SSE_STREAM_OUTCOMES.labels(name, "disconnected").inc()
        raise
    except Exception:
        SSE_STREAM_OUTCOMES.labels(name, "failed").inc()
        raise
    else:
        SSE_STREAM_OUTCOMES.labels(name, "completed").inc()
