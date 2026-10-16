import pytest

from app.core.errors import PermissionDeniedError
from app.core.security.firebase_token import FirebaseUser
from app.core.security.tenant_context import resolve_tenant_context


class _FakeMembershipsRepo:
    def __init__(self, membership: dict | None) -> None:
        self._membership = membership
        self.calls = 0

    async def find_active_for_user(self, uid: str, org_id: str) -> dict | None:
        self.calls += 1
        return self._membership


async def test_resolve_tenant_context_returns_role_from_membership() -> None:
    repo = _FakeMembershipsRepo({"role": "admin", "project_id": None})
    user = FirebaseUser(uid="rtc-u1", email="u1@example.com")

    context = await resolve_tenant_context(user, "rtc-org1", repo)

    assert context.uid == "rtc-u1"
    assert context.org_id == "rtc-org1"
    assert context.role == "admin"


async def test_resolve_tenant_context_raises_when_not_a_member() -> None:
    repo = _FakeMembershipsRepo(None)
    user = FirebaseUser(uid="rtc-u2", email=None)

    with pytest.raises(PermissionDeniedError):
        await resolve_tenant_context(user, "rtc-org2", repo)


async def test_resolve_tenant_context_caches_result() -> None:
    repo = _FakeMembershipsRepo({"role": "member", "project_id": None})
    user = FirebaseUser(uid="rtc-u3", email=None)

    await resolve_tenant_context(user, "rtc-org3", repo)
    await resolve_tenant_context(user, "rtc-org3", repo)

    assert repo.calls == 1
