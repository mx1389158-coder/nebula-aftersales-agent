from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.core.security import create_access_token, verify_password
from apps.api.app.models import User
from apps.api.app.schemas import LoginRequest, Principal, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db)) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    return TokenResponse(
        access_token=create_access_token(
            Principal(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
        )
    )


@router.post("/demo-token", response_model=TokenResponse)
def demo_token(session: Session = Depends(get_db)) -> TokenResponse:
    if not settings.demo_mode:
        raise HTTPException(status_code=404, detail="演示登录已关闭")
    user = session.scalar(
        select(User).where(User.tenant_id == "demo").order_by(User.created_at.asc())
    )
    if not user:
        raise HTTPException(status_code=503, detail="演示用户未初始化")
    token = create_access_token(
        Principal(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
    )
    return TokenResponse(access_token=token)
