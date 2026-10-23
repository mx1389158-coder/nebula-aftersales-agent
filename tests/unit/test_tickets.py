from sqlalchemy.orm import Session

from packages.tools.tickets import TicketTools


def test_ticket_requires_confirmation_and_is_idempotent(session: Session) -> None:
    tools = TicketTools(session)
    first = tools.create_ticket(
        tenant_id="tenant-1",
        user_id="user-1",
        summary="路由器无法取得 WAN 地址",
        contact="13800000000",
        idempotency_key="request-0001",
        confirmed=False,
    )
    assert first.status == "need_confirm"

    created = tools.create_ticket(
        tenant_id="tenant-1",
        user_id="user-1",
        summary="路由器无法取得 WAN 地址",
        contact="13800000000",
        idempotency_key="request-0001",
        confirmed=True,
    )
    repeated = tools.create_ticket(
        tenant_id="tenant-1",
        user_id="user-1",
        summary="这段摘要不会覆盖原工单",
        contact="13800000000",
        idempotency_key="request-0001",
        confirmed=True,
    )
    assert created.status == "success"
    assert repeated.data["ticket_id"] == created.data["ticket_id"]
    assert repeated.data["deduplicated"] is True
