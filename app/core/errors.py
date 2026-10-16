"""Domain exceptions and their single mapping to HTTP responses.

Services raise these; `register_exception_handlers` (called once from
app.main) maps them to HTTP responses. Route handlers never catch a domain
exception and build their own error response — that would duplicate this
mapping per route.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 500

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class NotFoundError(DomainError):
    status_code = 404


class PermissionDeniedError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409


class QuotaExceededError(DomainError):
    status_code = 402


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"error": exc.message, **exc.context}
        )
