from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal
from apps.api.app.models import AuditLog, Memory, User
from apps.api.app.schemas import (
    MemoryCreate,
    MemoryUpdate,
    MemoryView,
    Principal,
    UserSettingsUpdate,
)
from packages.context.memory import GovernedMemoryStore

router = APIRouter()


@router.get("/settings")
def get_memory_settings(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_db)
) -> dict[str, bool]:
    user = session.scalar(
        select(User).where(User.id == principal.user_id, User.tenant_id == principal.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"auto_memory_enabled": user.auto_memory_enabled}


@router.patch("/settings")
def update_memory_settings(
    payload: UserSettingsUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, bool]:
    user = session.scalar(
        select(User).where(User.id == principal.user_id, User.tenant_id == principal.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.auto_memory_enabled = payload.auto_memory_enabled
    session.commit()
    return {"auto_memory_enabled": user.auto_memory_enabled}


@router.get("", response_model=list[MemoryView])
def list_memories(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_db)
) -> list[Memory]:
    return list(
        session.scalars(
            select(Memory)
            .where(Memory.tenant_id == principal.tenant_id, Memory.user_id == principal.user_id)
            .order_by(Memory.updated_at.desc())
        )
    )


@router.post("", response_model=MemoryView, status_code=201)
def create_memory(
    payload: MemoryCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> Memory:
    try:
        return GovernedMemoryStore(session).add(
            tenant_id=principal.tenant_id, user_id=principal.user_id, **payload.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{memory_id}", response_model=MemoryView)
def update_memory(
    memory_id: str,
    payload: MemoryUpdate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> Memory:
    memory = session.scalar(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.tenant_id == principal.tenant_id,
            Memory.user_id == principal.user_id,
        )
    )
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    try:
        return GovernedMemoryStore(session).update(
            memory,
            actor_id=principal.user_id,
            changes=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{memory_id}", status_code=204)
def delete_memory(
    memory_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> Response:
    memory = session.scalar(
        select(Memory).where(
            Memory.id == memory_id,
            Memory.tenant_id == principal.tenant_id,
            Memory.user_id == principal.user_id,
        )
    )
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    memory.status = "deleted"
    memory.fact = "[已由用户删除]"
    session.add(
        AuditLog(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="memory.delete",
            entity_type="memory",
            entity_id=memory.id,
        )
    )
    session.commit()
    return Response(status_code=204)
