"""Shared FastAPI dependencies. This is the only place request-level auth
wiring happens — route modules only declare `Depends(...)` from here, never
call firebase_token/tenant_context/rbac directly.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Header

from app.core.errors import PermissionDeniedError
from app.core.firestore_client import get_firestore_client
from app.core.security import rbac
from app.core.security.firebase_token import FirebaseUser, verify_id_token
from app.core.security.tenant_context import TenantContext, resolve_tenant_context
from app.repositories.memberships_repo import MembershipsRepository
from app.repositories.orgs_repo import OrgsRepository
from app.repositories.users_repo import UsersRepository


def get_memberships_repo() -> MembershipsRepository:
    return MembershipsRepository(get_firestore_client())


def get_orgs_repo() -> OrgsRepository:
    return OrgsRepository(get_firestore_client())


def get_users_repo() -> UsersRepository:
    return UsersRepository(get_firestore_client())


async def get_current_user(authorization: str = Header(...)) -> FirebaseUser:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise PermissionDeniedError("Expected 'Authorization: Bearer <token>'")
    return verify_id_token(token)


async def get_tenant_context(
    org_id: str,
    user: FirebaseUser = Depends(get_current_user),
    memberships_repo: MembershipsRepository = Depends(get_memberships_repo),
) -> TenantContext:
    return await resolve_tenant_context(user, org_id, memberships_repo)


def require_role(minimum: str) -> Callable[..., Awaitable[TenantContext]]:
    checker = rbac.require_role(minimum)

    async def _dependency(tenant: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        return checker(tenant)

    return _dependency
