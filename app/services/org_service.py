"""Org/membership business logic — app/api/v1/orgs.py calls into this and
implements no logic itself. Role authorization is already enforced once,
at the route's `require_role(...)` dependency (see app/api/deps.py); the
checks below are domain rules, not a second authorization layer.
"""
from __future__ import annotations

from typing import Any

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security.tenant_context import TenantContext
from app.repositories.memberships_repo import MembershipsRepository
from app.repositories.orgs_repo import OrgsRepository


async def create_org(
    uid: str, name: str, orgs_repo: OrgsRepository, memberships_repo: MembershipsRepository
) -> dict[str, Any]:
    org = await orgs_repo.create(owner_uid=uid, name=name)
    await memberships_repo.create(org_id=org["id"], uid=uid, role="owner")
    return org


async def get_org(tenant: TenantContext, orgs_repo: OrgsRepository) -> dict[str, Any]:
    org = await orgs_repo.get_for_tenant(tenant)
    if org is None:
        raise NotFoundError("Organization not found", org_id=tenant.org_id)
    return org


async def list_members(
    tenant: TenantContext, memberships_repo: MembershipsRepository
) -> list[dict[str, Any]]:
    return await memberships_repo.list_scoped(tenant)


async def invite_member(
    tenant: TenantContext, uid: str, role: str, memberships_repo: MembershipsRepository
) -> dict[str, Any]:
    if role == "owner":
        raise PermissionDeniedError("Cannot invite a member directly as owner")
    existing = await memberships_repo.find_active_for_user(uid=uid, org_id=tenant.org_id)
    if existing is not None:
        raise ConflictError("User is already a member of this organization", uid=uid)
    return await memberships_repo.create(org_id=tenant.org_id, uid=uid, role=role)


async def change_member_role(
    tenant: TenantContext,
    membership_id: str,
    new_role: str,
    memberships_repo: MembershipsRepository,
) -> None:
    if new_role == "owner":
        raise PermissionDeniedError("Ownership transfer is not supported yet")
    await memberships_repo.update_role(tenant, membership_id, new_role)


async def remove_member(
    tenant: TenantContext, membership_id: str, memberships_repo: MembershipsRepository
) -> None:
    membership = await memberships_repo.get_scoped(tenant, membership_id)
    if membership is None:
        raise NotFoundError("Membership not found", membership_id=membership_id)
    if membership["role"] == "owner":
        raise PermissionDeniedError("Cannot remove the organization owner")
    await memberships_repo.deactivate(tenant, membership_id)
