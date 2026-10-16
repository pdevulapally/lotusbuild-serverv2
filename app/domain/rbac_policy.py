"""Role -> rank data. A permission check is a dict lookup, never an
if/elif chain — adding a role means editing this data, not scattering new
conditionals through route/service code. See docs/ARCHITECTURE.md §4.
"""
from __future__ import annotations

ROLE_RANK: dict[str, int] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
    "owner": 3,
}


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[minimum]
