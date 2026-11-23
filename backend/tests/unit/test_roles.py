import uuid

import pytest
from fastapi import HTTPException

from sp.api.deps import CurrentUser, require_role


def _user(role: str) -> CurrentUser:
    return CurrentUser(user_id=uuid.uuid4(), email="x@example.com", organization_id=uuid.uuid4(), role=role)


def test_require_role_rejects_other_role() -> None:
    checker = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        checker(current_user=_user("read_only"))

    assert exc_info.value.status_code == 403


def test_require_role_passes_through_allowed_user() -> None:
    checker = require_role("admin", "commercial")
    user = _user("commercial")

    assert checker(current_user=user) is user
