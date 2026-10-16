"""Generic tenant-scoped Firestore access. A repository method that reads
existing data takes a TenantContext and is scoped through here — no
individual repository hand-writes an `org_id` filter. The few operations
that legitimately run before a TenantContext exists (creating an org,
resolving a user's own memberships) are not tenant-scoped by nature and
live in their own repository methods instead — see orgs_repo.py and
memberships_repo.py for the documented exceptions.
"""
from __future__ import annotations

from typing import Any

from google.cloud.firestore import AsyncClient, FieldFilter

from app.core.security.tenant_context import TenantContext


class TenantScopedRepository:
    collection_name: str

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    def _collection(self) -> Any:
        return self._client.collection(self.collection_name)

    async def get_scoped(self, tenant: TenantContext, doc_id: str) -> dict[str, Any] | None:
        snapshot = await self._collection().document(doc_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        if data.get("org_id") != tenant.org_id:
            return None
        return {"id": snapshot.id, **data}

    async def list_scoped(self, tenant: TenantContext) -> list[dict[str, Any]]:
        query = self._collection().where(filter=FieldFilter("org_id", "==", tenant.org_id))
        return [{"id": doc.id, **(doc.to_dict() or {})} async for doc in query.stream()]
