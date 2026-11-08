from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.models import User
from apps.api.app.schemas import Principal

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, *, salt: str | None = None) -> str:
    value_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(value_salt), 210_000)
    return f"pbkdf2_sha256$210000${value_salt}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_access_token(principal: Principal) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": principal.user_id,
        "tenant_id": principal.tenant_id,
        "role": principal.role,
        "roles": [principal.role.upper()],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_user_id: str | None = Header(default=None),
    x_tenant_id: str = Header(default="demo"),
    session: Session = Depends(get_db),
) -> Principal:
    if credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.secret_key,
                algorithms=["HS256"],
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
            principal = Principal(
                user_id=str(payload["sub"]),
                tenant_id=str(payload["tenant_id"]),
                role=str(payload.get("role", "user")).lower(),
                access_token=credentials.credentials,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的访问令牌"
            ) from exc
    elif settings.demo_mode and x_user_id:
        principal = Principal(user_id=x_user_id, tenant_id=x_tenant_id)
    elif settings.demo_mode:
        user = session.scalar(
            select(User).where(User.tenant_id == "demo").order_by(User.created_at.asc())
        )
        if not user:
            raise HTTPException(status_code=503, detail="演示用户尚未初始化")
        principal = Principal(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录")

    user = session.scalar(
        select(User).where(
            User.id == principal.user_id,
            User.tenant_id == principal.tenant_id,
            User.is_active.is_(True),
        )
    )
    if not user and credentials and settings.business_service_enabled:
        # AI tables retain a minimal identity projection for foreign keys only.
        # Authentication and all business authorization remain owned by Java.
        user = User(
            id=principal.user_id,
            tenant_id=principal.tenant_id,
            email=f"java-{principal.user_id}@identity.local",
            display_name=str(payload.get("username", "业务服务用户")),
            role=principal.role,
            is_active=True,
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            # Multiple first requests for the same Java identity can arrive in
            # parallel during UI bootstrap. The winning transaction owns the
            # projection; losing requests roll back and reuse that committed row.
            session.rollback()
            user = session.scalar(
                select(User).where(
                    User.id == principal.user_id,
                    User.tenant_id == principal.tenant_id,
                    User.is_active.is_(True),
                )
            )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    return Principal(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=principal.role if credentials else user.role,
        access_token=principal.access_token,
    )


def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return principal


def require_staff(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.role not in {"admin", "support"}:
        raise HTTPException(status_code=403, detail="需要管理员或售后权限")
    return principal
