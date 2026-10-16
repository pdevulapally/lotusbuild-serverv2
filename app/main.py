"""FastAPI application entrypoint. See docs/ARCHITECTURE.md for the full
system design — this file only wires together what later phases add and
contains no business logic itself.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.core.errors import register_exception_handlers
from app.core.redis_client import close_redis, get_redis


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    await get_redis().ping()
    yield
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(title="Lotusbuild Backend", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
