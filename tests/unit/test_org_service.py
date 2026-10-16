import pytest

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.core.security.tenant_context import TenantContext
from app.services import org_service


class _FakeMembershipsRepo:
    def __init__(self) -> None:
        self.memberships: dict[str, dict] = {}

    async def find_active_for_user(self, uid: str, org_id: str) -> dict | None:
        for membership in self.memberships.values():
            if (
                membership["uid"] == uid
                and membership["org_id"] == org_id
                and membership["status"] == "active"
                and membership.get("project_id") is None
            ):
                return membership
        return None

    async def create(self, org_id: str, uid: str, role: str, project_id: str | None = None) -> dict:
        membership_id = f"m{len(self.memberships) + 1}"
        data = {
            "id": membership_id,
            "org_id": org_id,
            "uid": uid,
            "role": role,
            "project_id": project_id,
            "status": "active",
        }
        self.memberships[membership_id] = data
        return data

    async def get_scoped(self, tenant: TenantContext, doc_id: str) -> dict | None:
        membership = self.memberships.get(doc_id)
        if membership is None or membership["org_id"] != tenant.org_id:
            return None
        return membership

    async def update_role(self, tenant: TenantContext, membership_id: str, role: str) -> None:
        if await self.get_scoped(tenant, membership_id) is not None:
            self.memberships[membership_id]["role"] = role

    async def deactivate(self, tenant: TenantContext, membership_id: str) -> None:
        if await self.get_scoped(tenant, membership_id) is not None:
            self.memberships[membership_id]["status"] = "removed"


def _tenant(org_id: str = "org1", role: str = "admin") -> TenantContext:
    return TenantContext(uid="u1", org_id=org_id, role=role)


async def test_invite_member_rejects_owner_role() -> None:
    repo = _FakeMembershipsRepo()
    with pytest.raises(PermissionDeniedError):
        await org_service.invite_member(_tenant(), "u2", "owner", repo)


async def test_invite_member_rejects_duplicate_membership() -> None:
    repo = _FakeMembershipsRepo()
    await repo.create(org_id="org1", uid="u2", role="member")

    with pytest.raises(ConflictError):
        await org_service.invite_member(_tenant(), "u2", "member", repo)


async def test_invite_member_succeeds() -> None:
    repo = _FakeMembershipsRepo()
    membership = await org_service.invite_member(_tenant(), "u2", "member", repo)
    assert membership["role"] == "member"


async def test_change_member_role_rejects_promotion_to_owner() -> None:
    repo = _FakeMembershipsRepo()
    membership = await repo.create(org_id="org1", uid="u2", role="member")

    with pytest.raises(PermissionDeniedError):
        await org_service.change_member_role(_tenant(), membership["id"], "owner", repo)


async def test_remove_member_rejects_removing_owner() -> None:
    repo = _FakeMembershipsRepo()
    membership = await repo.create(org_id="org1", uid="owner-uid", role="owner")

    with pytest.raises(PermissionDeniedError):
        await org_service.remove_member(_tenant(), membership["id"], repo)


async def test_remove_member_not_found() -> None:
    repo = _FakeMembershipsRepo()
    with pytest.raises(NotFoundError):
        await org_service.remove_member(_tenant(), "missing-id", repo)
