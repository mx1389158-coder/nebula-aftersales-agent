from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal
from apps.api.app.models import AgentCheckpoint, Conversation, Message
from apps.api.app.schemas import ChatRequest, ChatResponse, Citation, Principal, ResumeRequest
from packages.agent_core import AgentRuntime

router = APIRouter()


def _context(session: Session, conversation: Conversation) -> list[str]:
    recent = list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(12)
        )
    )
    values = [f"历史摘要：{conversation.summary}"] if conversation.summary else []
    values.extend(f"{item.role}: {item.content}" for item in reversed(recent) if item.content)
    return values


def _compact(session: Session, conversation: Conversation) -> None:
    messages = list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
    )
    threshold = settings.conversation_summary_threshold
    if len(messages) <= threshold:
        return
    older = messages[:-12]
    digest = "；".join(f"{item.role}:{item.content[:160]}" for item in older if item.content)
    conversation.summary = digest[-4000:] if digest else conversation.summary


def _run_chat(request: ChatRequest, principal: Principal, session: Session) -> ChatResponse:
    thread_id = request.thread_id or str(uuid.uuid4())
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
    )
    if not conversation:
        conversation = Conversation(
            thread_id=thread_id,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            title=request.message[:80],
        )
        session.add(conversation)
        session.flush()
    conversation.status = "active"
    conversation_context = _context(session, conversation)
    session.add(Message(conversation_id=conversation.id, role="user", content=request.message))
    result = AgentRuntime(session).invoke(
        {
            **request.model_dump(),
            "thread_id": thread_id,
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
            "access_token": principal.access_token,
            "conversation_context": conversation_context,
        }
    )
    citations = [
        Citation(
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            title=item.title,
            section=item.section,
            version=item.version,
            page=item.page,
            score=item.score,
            excerpt=item.text[:180],
        )
        for item in result.get("evidence", [])
    ]
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result["answer"],
        trace_id=result["request_id"],
        citations=[item.model_dump() for item in citations],
    )
    session.add(assistant_message)
    _compact(session, conversation)
    session.commit()
    return ChatResponse(
        request_id=result["request_id"],
        message_id=assistant_message.id,
        thread_id=thread_id,
        decision=result["decision"],
        answer=result["answer"],
        citations=citations,
        trace=result.get("trace", []),
        tool_result=result.get("tool_result"),
        pending_action=result.get("pending_action"),
        handoff_id=result.get("handoff_id"),
    )


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> ChatResponse:
    return _run_chat(request, principal, session)


@router.post("/{thread_id}/resume", response_model=ChatResponse)
def resume_chat(
    thread_id: str,
    request: ResumeRequest,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> ChatResponse:
    checkpoint = session.scalar(
        select(AgentCheckpoint).where(
            AgentCheckpoint.thread_id == thread_id,
            AgentCheckpoint.tenant_id == principal.tenant_id,
            AgentCheckpoint.user_id == principal.user_id,
        )
    )
    if not checkpoint or not checkpoint.pending_action:
        raise HTTPException(status_code=409, detail="该会话没有等待恢复的操作")
    pending = checkpoint.pending_action
    return _run_chat(
        ChatRequest(
            message=request.message
            or str(pending.get("summary") or pending.get("fact") or "恢复操作"),
            thread_id=thread_id,
            device_id=pending.get("device_id"),
            confirmed=request.confirmed,
            contact=request.contact or pending.get("contact"),
            idempotency_key=pending.get("idempotency_key"),
        ),
        principal,
        session,
    )


@router.get("/{thread_id}/status")
def chat_status(
    thread_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    checkpoint = session.scalar(
        select(AgentCheckpoint).where(
            AgentCheckpoint.thread_id == thread_id,
            AgentCheckpoint.tenant_id == principal.tenant_id,
            AgentCheckpoint.user_id == principal.user_id,
        )
    )
    return {
        "thread_id": thread_id,
        "status": conversation.status,
        "checkpoint_status": checkpoint.status if checkpoint else "idle",
        "pending_action": checkpoint.pending_action if checkpoint else {},
    }


@router.post("/{thread_id}/cancel")
def cancel_chat(
    thread_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.thread_id == thread_id,
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    checkpoint = session.scalar(
        select(AgentCheckpoint).where(
            AgentCheckpoint.thread_id == thread_id,
            AgentCheckpoint.tenant_id == principal.tenant_id,
            AgentCheckpoint.user_id == principal.user_id,
        )
    )
    conversation.status = "cancelled"
    if checkpoint:
        checkpoint.status = "cancelled"
        checkpoint.pending_action = {}
    session.commit()
    return {"thread_id": thread_id, "status": "cancelled"}


@router.post("/stream")
def chat_stream(
    request: ChatRequest,
    raw_request: Request,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        thread_id = request.thread_id or str(uuid.uuid4())
        conversation = session.scalar(
            select(Conversation).where(
                Conversation.thread_id == thread_id,
                Conversation.tenant_id == principal.tenant_id,
                Conversation.user_id == principal.user_id,
            )
        )
        if not conversation:
            conversation = Conversation(
                thread_id=thread_id,
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                title=request.message[:80],
            )
            session.add(conversation)
            session.flush()
        conversation.status = "active"
        conversation_context = _context(session, conversation)
        session.add(Message(conversation_id=conversation.id, role="user", content=request.message))
        runtime = AgentRuntime(session)
        result = runtime.invoke(
            {
                **request.model_dump(),
                "thread_id": thread_id,
                "tenant_id": principal.tenant_id,
                "user_id": principal.user_id,
                "access_token": principal.access_token,
                "conversation_context": conversation_context,
                "_defer_answer": True,
            }
        )
        citations = [
            Citation(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                title=item.title,
                section=item.section,
                version=item.version,
                page=item.page,
                score=item.score,
                excerpt=item.text[:180],
            )
            for item in result.get("evidence", [])
        ]
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="",
            trace_id=result["request_id"],
            citations=[item.model_dump() for item in citations],
        )
        session.add(assistant_message)
        session.flush()
        yield f"event: meta\ndata: {json.dumps({'request_id': result['request_id'], 'message_id': assistant_message.id, 'thread_id': thread_id, 'decision': result['decision'], 'pending_action': result.get('pending_action') or None, 'tool_result': result.get('tool_result'), 'handoff_id': result.get('handoff_id')}, ensure_ascii=False)}\n\n"
        parts: list[str] = []
        if result["decision"] == "ANSWER":
            skill_steps = [
                str(step) for skill in result.get("skills", []) for step in skill.get("steps", [])
            ]
            tokens = runtime.provider.stream(
                request.message,
                result.get("evidence", []),
                [
                    *result.get("conversation_context", []),
                    *result.get("memories", []),
                    *skill_steps[:3],
                ],
            )
        else:
            answer = result.get("answer", "")
            tokens = (answer[offset : offset + 18] for offset in range(0, len(answer), 18))
        disconnected = False
        try:
            for token in tokens:
                if await raw_request.is_disconnected():
                    disconnected = True
                    break
                parts.append(token)
                yield f"event: token\ndata: {json.dumps({'text': token}, ensure_ascii=False)}\n\n"
        finally:
            close = getattr(tokens, "close", None)
            if close:
                close()
            assistant_message.content = "".join(parts)
            _compact(session, conversation)
            session.commit()
        if disconnected:
            return
        yield f"event: citations\ndata: {json.dumps([item.model_dump() for item in citations], ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
