from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal, require_staff
from apps.api.app.models import (
    Conversation,
    Feedback,
    HumanHandoff,
    Message,
    Skill,
    SkillVersion,
)
from apps.api.app.schemas import FeedbackCreate, HandoffUpdate, Principal
from apps.api.app.services.skills import validate_skill

router = APIRouter()


@router.post("/feedback", status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict:
    message = session.scalar(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == payload.message_id,
            Message.role == "assistant",
            Conversation.tenant_id == principal.tenant_id,
            Conversation.user_id == principal.user_id,
        )
    )
    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")
    feedback = Feedback(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        message_id=message.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    session.add(feedback)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="该消息已经评价") from exc
    candidate_id: str | None = None
    if payload.rating == 1 and message.citations:
        steps = [
            {"action": "使用已验证知识证据回答", "chunk_id": item.get("chunk_id")}
            for item in message.citations[:5]
        ]
        tests = [{"input": message.content[:500], "expected_decision": "ANSWER"}]
        constraints = {"max_steps": 8, "requires_citation": True}
        report = validate_skill(steps, tests, constraints)
        skill = Skill(
            tenant_id=principal.tenant_id,
            name=f"成功会话候选-{message.id[:8]}",
            scope={"source_message_id": message.id},
            status="candidate",
        )
        session.add(skill)
        session.flush()
        session.add(
            SkillVersion(
                skill_id=skill.id,
                version=1,
                steps=steps,
                tests=tests,
                constraints=constraints,
                test_report=report,
            )
        )
        candidate_id = skill.id
    session.commit()
    return {"id": feedback.id, "candidate_skill_id": candidate_id}


@router.get("/handoffs")
def list_handoffs(
    principal: Principal = Depends(require_staff), session: Session = Depends(get_db)
) -> list[dict]:
    rows = session.scalars(
        select(HumanHandoff)
        .where(HumanHandoff.tenant_id == principal.tenant_id)
        .order_by(HumanHandoff.created_at.desc())
    )
    return [
        {
            "id": item.id,
            "thread_id": item.thread_id,
            "reason": item.reason,
            "context": item.context,
            "status": item.status,
            "assigned_to": item.assigned_to,
            "created_at": item.created_at,
        }
        for item in rows
    ]


@router.patch("/handoffs/{handoff_id}")
def update_handoff(
    handoff_id: str,
    payload: HandoffUpdate,
    principal: Principal = Depends(require_staff),
    session: Session = Depends(get_db),
) -> dict:
    handoff = session.scalar(
        select(HumanHandoff).where(
            HumanHandoff.id == handoff_id, HumanHandoff.tenant_id == principal.tenant_id
        )
    )
    if not handoff:
        raise HTTPException(status_code=404, detail="转接记录不存在")
    handoff.status = payload.status
    handoff.assigned_to = payload.assigned_to or handoff.assigned_to
    session.commit()
    return {"id": handoff.id, "status": handoff.status, "assigned_to": handoff.assigned_to}
