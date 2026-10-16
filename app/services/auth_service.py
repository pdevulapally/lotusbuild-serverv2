"""Bootstraps a Firestore user profile for a verified Firebase identity.
Firebase handles login itself — this just ensures users/{uid} exists.
"""
from __future__ import annotations

from typing import Any

from app.core.security.firebase_token import FirebaseUser
from app.repositories.users_repo import UsersRepository


async def ensure_user_profile(user: FirebaseUser, users_repo: UsersRepository) -> dict[str, Any]:
    return await users_repo.ensure_exists(uid=user.uid, email=user.email)
