"""Resolves the authenticated request's tenant/role. This is the ONLY place
a request's org_id/role is decided, and it is never derived from a
client-supplied org_id alone — it comes from a live membership lookup
keyed by the verified Firebase uid. See docs/ARCHITECTURE.md §4.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from app.config import settings
from app.core.errors import PermissionDeniedError
from app.core.security.firebase_token import FirebaseUser


@dataclass(frozen=True)
class TenantContext:
    uid: str
    org_id: str
    role: str
    project_id: str | None = None


class MembershipLookup(Protocol):
    async def find_active_for_user(self, uid: str, org_id: str) -> dict | None: ...


class _TTLCache:
    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[tuple[str, str], tuple[float, TenantContext]] = {}

    def get(self, key: tuple[str, str]) -> TenantContext | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: tuple[str, str], value: TenantContext) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)


_cache = _TTLCache(settings.tenant_cache_ttl_seconds)


async def resolve_tenant_context(
    user: FirebaseUser, org_id: str, memberships_repo: MembershipLookup
) -> TenantContext:
    cache_key = (user.uid, org_id)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    membership = await memberships_repo.find_active_for_user(uid=user.uid, org_id=org_id)
    if membership is None:
        raise PermissionDeniedError("Not a member of this organization", org_id=org_id)

    context = TenantContext(
        uid=user.uid,
        org_id=org_id,
        role=membership["role"],
        project_id=membership.get("project_id"),
    )
    _cache.set(cache_key, context)
    return context
