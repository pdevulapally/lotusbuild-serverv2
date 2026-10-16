"""Org/membership REST endpoints. Transport only — all logic lives in
app/services/org_service.py.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_memberships_repo, get_orgs_repo, require_role
from app.core.security.firebase_token import FirebaseUser
from app.core.security.tenant_context import TenantContext
from app.repositories.memberships_repo import MembershipsRepository
from app.repositories.orgs_repo import OrgsRepository
from app.services import org_service

router = APIRouter(prefix="/orgs", tags=["orgs"])

Role = Literal["viewer", "member", "admin"]


class CreateOrgRequest(BaseModel):
    name: str


class InviteMemberRequest(BaseModel):
    uid: str
    role: Role


class ChangeRoleRequest(BaseModel):
    role: Role


@router.post("")
async def create_org(
    body: CreateOrgRequest,
    user: FirebaseUser = Depends(get_current_user),
    orgs_repo: OrgsRepository = Depends(get_orgs_repo),
    memberships_repo: MembershipsRepository = Depends(get_memberships_repo),
) -> dict[str, Any]:
    return await org_service.create_org(user.uid, body.name, orgs_repo, memberships_repo)


@router.get("/{org_id}")
async def get_org(
    tenant: TenantContext = Depends(require_role("viewer")),
    orgs_repo: OrgsRepository = Depends(get_orgs_repo),
) -> dict[str, Any]:
    return await org_service.get_org(tenant, orgs_repo)


@router.get("/{org_id}/members")
async def list_members(
    tenant: TenantContext = Depends(require_role("viewer")),
    memberships_repo: MembershipsRepository = Depends(get_memberships_repo),
) -> list[dict[str, Any]]:
    return await org_service.list_members(tenant, memberships_repo)


@router.post("/{org_id}/members")
async def invite_member(
    body: InviteMemberRequest,
    tenant: TenantContext = Depends(require_role("admin")),
    memberships_repo: MembershipsRepository = Depends(get_memberships_repo),
) -> dict[str, Any]:
    return await org_service.invite_member(tenant, body.uid, body.role, memberships_repo)


@router.patch("/{org_id}/members/{membership_id}")
async def change_member_role(
    membership_id: str,
    body: ChangeRoleRequest,
    tenant: TenantContext = Depends(require_role("owner")),
    memberships_repo: MembershipsRepository = Depends(get_memberships_repo),
) -> None:
    await org_service.change_member_role(tenant, membership_id, body.role, memberships_repo)


@router.delete("/{org_id}/members/{membership_id}")
async def remove_member(
    membership_id: str,
    tenant: TenantContext = Depends(require_role("admin")),
    memberships_repo: MembershipsRepository = Depends(get_memberships_repo),
) -> None:
    await org_service.remove_member(tenant, membership_id, memberships_repo)
