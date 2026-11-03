from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal
from apps.api.app.models import Conversation, Message
from apps.api.app.schemas import Principal

router = APIRouter()


@router.get("")
def list_conversations(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_db)
) -> list[dict[str, object]]:
    rows = session.scalars(
        select(Conversation)
        .where(
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
        .order_by(Conversation.updated_at.desc())
        .limit(100)
    )
    return [
        {
            "thread_id": row.thread_id,
            "title": row.title,
            "status": row.status,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.get("/{thread_id}")
def get_conversation(
    thread_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    row = session.scalar(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = session.scalars(
        select(Message).where(Message.conversation_id == row.id).order_by(Message.created_at)
    )
    return {
        "thread_id": row.thread_id,
        "title": row.title,
        "status": row.status,
        "messages": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "trace_id": item.trace_id,
                "citations": item.citations,
                "created_at": item.created_at,
            }
            for item in messages
        ],
    }
