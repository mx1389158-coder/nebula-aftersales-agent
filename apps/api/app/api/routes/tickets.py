from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal, require_admin
from apps.api.app.models import Ticket, TicketEvent
from apps.api.app.schemas import Principal, TicketCreate, TicketUpdate, TicketView
from packages.tools.tickets import TicketTools

router = APIRouter()


@router.get("", response_model=list[TicketView])
def list_tickets(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_db)
) -> list[Ticket]:
    return list(
        session.scalars(
            select(Ticket)
            .where(Ticket.tenant_id == principal.tenant_id, Ticket.user_id == principal.user_id)
            .order_by(Ticket.updated_at.desc())
        )
    )


@router.post("", response_model=dict, status_code=201)
def create_ticket(
    payload: TicketCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict:
    result = TicketTools(session).create_ticket(
        tenant_id=principal.tenant_id, user_id=principal.user_id, **payload.model_dump()
    )
    if result.status == "need_confirm":
        raise HTTPException(status_code=409, detail=result.model_dump())
    if result.status != "success":
        raise HTTPException(status_code=404, detail=result.model_dump())
    return result.model_dump()


@router.get("/{ticket_id}", response_model=dict)
def ticket_status(
    ticket_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict:
    result = TicketTools(session).get_ticket_status(
        tenant_id=principal.tenant_id, user_id=principal.user_id, ticket_id=ticket_id
    )
    if result.status == "not_found":
        raise HTTPException(status_code=404, detail=result.message_for_model)
    return result.model_dump()


@router.patch("/{ticket_id}", response_model=TicketView)
def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> Ticket:
    ticket = session.scalar(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.tenant_id == principal.tenant_id)
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    previous = ticket.status
    ticket.status = payload.status
    ticket.events.append(
        TicketEvent(
            event_type="status_changed",
            detail={
                "from": previous,
                "to": payload.status,
                "note": payload.note,
                "actor_id": principal.user_id,
            },
        )
    )
    session.commit()
    session.refresh(ticket)
    return ticket
