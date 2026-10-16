"""Exercises the real create-org -> invite -> role-gated-access flow
against Firestore. Requires real Firebase credentials — run this on the
VPS (`pytest tests/integration`), not in CI. Uses a clearly-named test
org/account, never a real customer's, per docs/adr/0010.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.security.firebase_token import FirebaseUser
from app.main import app

pytestmark = pytest.mark.skipif(
    not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="requires real Firebase credentials — run on the VPS",
)


def _fake_user(uid: str) -> FirebaseUser:
    return FirebaseUser(uid=uid, email=f"{uid}@example.com")


def test_create_org_invite_and_role_gating() -> None:
    owner = _fake_user("integration-test-owner")
    member = _fake_user("integration-test-member")

    app.dependency_overrides[deps.get_current_user] = lambda: owner
    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/orgs", json={"name": "Integration Test Org"}
            )
            assert create_response.status_code == 200
            org_id = create_response.json()["id"]

            invite_response = client.post(
                f"/api/v1/orgs/{org_id}/members",
                json={"uid": member.uid, "role": "member"},
            )
            assert invite_response.status_code == 200

            app.dependency_overrides[deps.get_current_user] = lambda: member
            denied_response = client.post(
                f"/api/v1/orgs/{org_id}/members",
                json={"uid": "someone-else", "role": "viewer"},
            )
            assert denied_response.status_code == 403
    finally:
        app.dependency_overrides.clear()
