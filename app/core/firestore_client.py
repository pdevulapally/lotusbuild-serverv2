"""Single Firestore connection factory — mirrors core/redis_client.py.
Every repository is constructed with this client; none opens its own.

Credentials come from GOOGLE_APPLICATION_CREDENTIALS, read directly by
google-auth's own convention — not by app.config, since we never consume
its value ourselves (see docs/ARCHITECTURE.md §13 on secrets).
"""
from __future__ import annotations

from google.auth import default as google_auth_default
from google.cloud.firestore import AsyncClient

from app.config import settings

_client: AsyncClient | None = None


def get_firestore_client() -> AsyncClient:
    global _client
    if _client is None:
        credentials, _ = google_auth_default()
        _client = AsyncClient(project=settings.firebase_project_id, credentials=credentials)
    return _client
