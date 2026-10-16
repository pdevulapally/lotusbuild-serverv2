"""Organizations are the tenant boundary itself, not a tenant-scoped
resource within one — an org document has no `org_id` field, its own
document id IS the org_id. `create` is a deliberate exception to "every
repo method takes a TenantContext": there is no tenant context yet for an
org that doesn't exist.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import AsyncClient

from app.core.security.tenant_context import TenantContext

COLLECTION = "organizations"


class OrgsRepository:
    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def create(self, owner_uid: str, name: str) -> dict[str, Any]:
        org_id = str(uuid.uuid4())
        data = {
            "name": name,
            "owner_uid": owner_uid,
            "plan_id": None,  # set by billing_service once Phase 6 lands
            "stripe_customer_id": None,
            "created_at": datetime.now(UTC),
        }
        await self._client.collection(COLLECTION).document(org_id).set(data)
        return {"id": org_id, **data}

    async def get_by_id(self, org_id: str) -> dict[str, Any] | None:
        snapshot = await self._client.collection(COLLECTION).document(org_id).get()
        if not snapshot.exists:
            return None
        return {"id": snapshot.id, **(snapshot.to_dict() or {})}

    async def get_for_tenant(self, tenant: TenantContext) -> dict[str, Any] | None:
        return await self.get_by_id(tenant.org_id)
