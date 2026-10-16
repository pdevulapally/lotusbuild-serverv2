"""Memberships are `org_id`-tagged, so most reads go through the generic
tenant-scoped helpers in base.py. `find_active_for_user` is the one
deliberate exception: it's how a TenantContext gets constructed in the
first place, so it can't require one as input. See docs/adr/0007 for the
org-wide + per-project membership shape.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import FieldFilter

from app.core.security.tenant_context import TenantContext
from app.repositories.base import TenantScopedRepository

COLLECTION = "memberships"


class MembershipsRepository(TenantScopedRepository):
    collection_name = COLLECTION

    async def find_active_for_user(self, uid: str, org_id: str) -> dict[str, Any] | None:
        query = (
            self._collection()
            .where(filter=FieldFilter("uid", "==", uid))
            .where(filter=FieldFilter("org_id", "==", org_id))
            .where(filter=FieldFilter("status", "==", "active"))
        )
        org_wide: dict[str, Any] | None = None
        async for doc in query.stream():
            data = {"id": doc.id, **(doc.to_dict() or {})}
            if data.get("project_id") is None:
                org_wide = data
        return org_wide

    async def create(
        self, org_id: str, uid: str, role: str, project_id: str | None = None
    ) -> dict[str, Any]:
        membership_id = str(uuid.uuid4())
        data = {
            "org_id": org_id,
            "uid": uid,
            "role": role,
            "project_id": project_id,
            "status": "active",
            "created_at": datetime.now(UTC),
        }
        await self._collection().document(membership_id).set(data)
        return {"id": membership_id, **data}

    async def update_role(self, tenant: TenantContext, membership_id: str, role: str) -> None:
        if await self.get_scoped(tenant, membership_id) is None:
            return
        await self._collection().document(membership_id).update({"role": role})

    async def deactivate(self, tenant: TenantContext, membership_id: str) -> None:
        if await self.get_scoped(tenant, membership_id) is None:
            return
        await self._collection().document(membership_id).update({"status": "removed"})
