from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError

from apps.api.app.core.config import settings
from apps.api.app.core.security import get_principal, hash_password, verify_password
from apps.api.app.models import User


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)


def test_java_identity_projection_recovers_from_a_concurrent_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = "00000000-0000-0000-0000-000000000102"
    token = jwt.encode(
        {
            "sub": user_id,
            "tenant_id": "demo",
            "role": "SUPPORT",
            "username": "support@example.com",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm="HS256",
    )
    projected = User(
        id=user_id,
        tenant_id="demo",
        email="java-support@identity.local",
        display_name="support@example.com",
        role="support",
        is_active=True,
    )
    session = MagicMock()
    session.scalar.side_effect = [None, projected]
    session.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))
    monkeypatch.setattr(settings, "business_service_enabled", True)

    principal = get_principal(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        x_user_id=None,
        x_tenant_id="demo",
        session=session,
    )

    session.rollback.assert_called_once_with()
    assert principal.user_id == user_id
    assert principal.role == "support"
