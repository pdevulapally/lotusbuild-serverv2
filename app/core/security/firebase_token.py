"""Firebase ID token verification — the only implementation of it. Every
authenticated request (REST or WS) goes through `verify_id_token`.
"""
from __future__ import annotations

from dataclasses import dataclass

import firebase_admin
from firebase_admin import auth, credentials
from firebase_admin.exceptions import FirebaseError

from app.config import settings
from app.core.errors import PermissionDeniedError

_app: firebase_admin.App | None = None


def _get_firebase_app() -> firebase_admin.App:
    global _app
    if _app is None:
        _app = firebase_admin.initialize_app(
            credentials.ApplicationDefault(), {"projectId": settings.firebase_project_id}
        )
    return _app


@dataclass(frozen=True)
class FirebaseUser:
    uid: str
    email: str | None


def verify_id_token(id_token: str) -> FirebaseUser:
    try:
        decoded = auth.verify_id_token(id_token, app=_get_firebase_app())
    except FirebaseError as exc:
        raise PermissionDeniedError("Invalid or expired authentication token") from exc
    return FirebaseUser(uid=decoded["uid"], email=decoded.get("email"))
