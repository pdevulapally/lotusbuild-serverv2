"""Users are keyed by Firebase UID directly, not org-scoped — a user can
belong to many orgs. See docs/ARCHITECTURE.md §3.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient

COLLECTION = "users"


class UsersRepository:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def get(self, uid: str) -> dict[str, Any] | None:
        snapshot = await self._client.collection(COLLECTION).document(uid).get()
        return snapshot.to_dict() if snapshot.exists else None

    async def ensure_exists(self, uid: str, email: str | None) -> dict[str, Any]:
        existing = await self.get(uid)
        if existing is not None:
            return existing
        data = {"uid": uid, "email": email, "created_at": datetime.now(UTC)}
        await self._client.collection(COLLECTION).document(uid).set(data)
        return data
