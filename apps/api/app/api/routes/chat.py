from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal
from apps.api.app.models import Conversation, Message
from apps.api.app.schemas import ChatRequest, ChatResponse, Citation, Principal
from packages.agent_core import AgentRuntime

router = APIRouter()


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
    session.add(Message(conversation_id=conversation.id, role="user", content=request.message))
    result = AgentRuntime(session).invoke(
        {
            **request.model_dump(),
            "thread_id": thread_id,
            "tenant_id": principal.tenant_id,
            "user_id": principal.user_id,
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
        session.add(Message(conversation_id=conversation.id, role="user", content=request.message))
        runtime = AgentRuntime(session)
        result = runtime.invoke(
            {
                **request.model_dump(),
                "thread_id": thread_id,
                "tenant_id": principal.tenant_id,
                "user_id": principal.user_id,
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
                [*result.get("memories", []), *skill_steps[:3]],
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
            session.commit()
        if disconnected:
            return
        yield f"event: citations\ndata: {json.dumps([item.model_dump() for item in citations], ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
