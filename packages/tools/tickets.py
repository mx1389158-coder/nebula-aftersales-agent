from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models import Device, Ticket, TicketEvent
from packages.tools.contracts import ToolEvidence, ToolResult
from packages.tools.java_business import JavaBusinessClient


class TicketTools:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_ticket(
        self,
        *,
        tenant_id: str,
        user_id: str,
        summary: str,
        contact: str,
        idempotency_key: str,
        confirmed: bool,
        device_id: str | None = None,
        access_token: str | None = None,
        request_id: str | None = None,
    ) -> ToolResult:
        if settings.business_service_enabled:
            if not confirmed:
                return ToolResult(
                    status="need_confirm",
                    data={"summary": summary, "contact": contact, "device_id": device_id},
                    error_code="USER_CONFIRMATION_REQUIRED",
                    message_for_model="创建工单属于写操作，需要用户明确确认。",
                )
            if not access_token:
                return ToolResult(
                    status="failed",
                    error_code="MISSING_USER_TOKEN",
                    message_for_model="缺少调用业务服务所需的用户授权上下文。",
                )
            return JavaBusinessClient().create_ticket(
                access_token=access_token,
                summary=summary,
                contact=contact,
                idempotency_key=idempotency_key,
                device_id=device_id,
                request_id=request_id,
            )
        existing = self.session.scalar(
            select(Ticket).where(
                Ticket.tenant_id == tenant_id, Ticket.idempotency_key == idempotency_key
            )
        )
        if existing:
            return ToolResult(
                status="success",
                data={"ticket_id": existing.id, "status": existing.status, "deduplicated": True},
                message_for_model="已返回同一幂等请求创建的工单。",
                evidence=[ToolEvidence(type="db_record", id=existing.id)],
            )
        if not confirmed:
            return ToolResult(
                status="need_confirm",
                data={"summary": summary, "contact": contact},
                error_code="USER_CONFIRMATION_REQUIRED",
                message_for_model="创建工单属于写操作，需要用户明确确认。",
            )
        if device_id:
            owned = self.session.scalar(
                select(Device.id).where(
                    Device.id == device_id,
                    Device.tenant_id == tenant_id,
                    Device.user_id == user_id,
                )
            )
            if not owned:
                return ToolResult(
                    status="not_found",
                    error_code="DEVICE_NOT_OWNED",
                    message_for_model="设备不存在或不属于当前用户。",
                )
        ticket = Ticket(
            tenant_id=tenant_id,
            user_id=user_id,
            device_id=device_id,
            summary=summary,
            contact=contact,
            idempotency_key=idempotency_key,
        )
        ticket.events.append(TicketEvent(event_type="created", detail={"source": "assistant"}))
        self.session.add(ticket)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(Ticket).where(
                    Ticket.tenant_id == tenant_id, Ticket.idempotency_key == idempotency_key
                )
            )
            if not existing:
                raise
            ticket = existing
        self.session.refresh(ticket)
        return ToolResult(
            status="success",
            data={"ticket_id": ticket.id, "status": ticket.status, "deduplicated": False},
            message_for_model="工单创建成功。",
            evidence=[ToolEvidence(type="db_record", id=ticket.id)],
        )

    def get_ticket_status(
        self,
        *,
        tenant_id: str,
        user_id: str,
        ticket_id: str,
        access_token: str | None = None,
        request_id: str | None = None,
    ) -> ToolResult:
        if settings.business_service_enabled:
            if not access_token:
                return ToolResult(
                    status="failed",
                    error_code="MISSING_USER_TOKEN",
                    message_for_model="缺少调用业务服务所需的用户授权上下文。",
                )
            return JavaBusinessClient().get_ticket_status(
                access_token=access_token,
                ticket_id=ticket_id,
                request_id=request_id,
            )
        ticket = self.session.scalar(
            select(Ticket).where(
                Ticket.id == ticket_id,
                Ticket.tenant_id == tenant_id,
                Ticket.user_id == user_id,
            )
        )
        if not ticket:
            return ToolResult(status="not_found", message_for_model="未找到该工单。")
        return ToolResult(
            status="success",
            data={
                "ticket_id": ticket.id,
                "status": ticket.status,
                "updated_at": ticket.updated_at.isoformat(),
                "events": [
                    {
                        "type": event.event_type,
                        "detail": event.detail,
                        "created_at": event.created_at.isoformat(),
                    }
                    for event in sorted(ticket.events, key=lambda item: item.created_at)
                ],
            },
            message_for_model=f"工单当前状态为 {ticket.status}。",
            evidence=[ToolEvidence(type="db_record", id=ticket.id)],
        )
