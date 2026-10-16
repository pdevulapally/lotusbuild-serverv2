"""arq worker entrypoint, run as a separate process from the FastAPI server
(see docs/ARCHITECTURE.md §12). Task functions are registered here as each
phase adds them — Phase 4 (sandbox reaper), Phase 6 (Stripe webhook
processing, usage aggregation), Phase 7 (image builds). Empty until then.
"""
from __future__ import annotations

from arq.connections import RedisSettings

from app.config import settings


async def startup(ctx: dict) -> None:
    pass


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    functions: list = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
