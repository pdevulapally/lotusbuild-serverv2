"""Session bootstrap — Firebase handles login itself; this just ensures a
Firestore profile exists for the verified identity and returns it.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_users_repo
from app.core.security.firebase_token import FirebaseUser
from app.repositories.users_repo import UsersRepository
from app.services.auth_service import ensure_user_profile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_me(
    user: FirebaseUser = Depends(get_current_user),
    users_repo: UsersRepository = Depends(get_users_repo),
) -> dict[str, Any]:
    return await ensure_user_profile(user, users_repo)
