"""Pure RBAC check — framework-agnostic. app/api/deps.py binds this to a
FastAPI dependency; routes never check roles inline. See
docs/ARCHITECTURE.md §4.
"""
from __future__ import annotations

from collections.abc import Callable

from app.core.errors import PermissionDeniedError
from app.core.security.tenant_context import TenantContext
from app.domain.rbac_policy import role_at_least


def require_role(minimum: str) -> Callable[[TenantContext], TenantContext]:
    def _check(tenant: TenantContext) -> TenantContext:
        if not role_at_least(tenant.role, minimum):
            raise PermissionDeniedError(
                f"Requires role '{minimum}' or higher", role=tenant.role
            )
        return tenant

    return _check
