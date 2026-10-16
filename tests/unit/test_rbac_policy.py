from app.domain.rbac_policy import role_at_least


def test_role_at_least_allows_equal_and_higher() -> None:
    assert role_at_least("admin", "admin")
    assert role_at_least("owner", "admin")


def test_role_at_least_denies_lower() -> None:
    assert not role_at_least("viewer", "admin")


def test_role_at_least_denies_unknown_role() -> None:
    assert not role_at_least("not-a-role", "viewer")
