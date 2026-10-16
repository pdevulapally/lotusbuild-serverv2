"""Single Redis connection factory.

Reused by the task queue (arq, see app/workers/), the real-time event bus
(app/core/events.py, added in Phase 5), and any short-TTL caches — one
connection factory, not a new client constructed per module.
"""
from __future__ import annotations

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
