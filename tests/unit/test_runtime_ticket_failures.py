from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from packages.agent_core.providers import EvidenceTemplateProvider
from packages.agent_core.runtime import AgentRuntime
from packages.tools.contracts import ToolResult


class StubTicketTools:
    def __init__(self, results: list[ToolResult]) -> None:
        self._results: Iterator[ToolResult] = iter(results)
        self.calls: list[dict[str, object]] = []

    def create_ticket(self, **kwargs: object) -> ToolResult:
        self.calls.append(kwargs)
        return next(self._results)


def runtime_with_pending_ticket(session: Session, thread_id: str) -> AgentRuntime:
    runtime = AgentRuntime(session, EvidenceTemplateProvider())
    result = runtime.invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": thread_id,
            "message": "请创建工单处理设备无法联网",
            "contact": "user@example.invalid",
            "device_id": "device-from-pending",
        }
    )
    assert result["tool_result"]["status"] == "need_confirm"
    return runtime


@pytest.mark.parametrize(
    ("tool_result", "expected_status", "answer_fragment"),
    [
        (
            ToolResult(
                status="failed",
                error_code="BUSINESS_TIMEOUT",
                message_for_model="业务服务响应超时。",
            ),
            "failed",
            "创建失败",
        ),
        (
            ToolResult(
                status="failed",
                error_code="BUSINESS_HTTP_500",
                message_for_model="业务服务内部错误。",
            ),
            "failed",
            "创建失败",
        ),
        (
            ToolResult(
                status="not_found",
                error_code="DEVICE_NOT_OWNED",
                message_for_model="设备不存在或不属于当前用户。",
            ),
            "not_found",
            "不存在",
        ),
        (
            ToolResult(status="success", data={}, message_for_model="业务服务操作成功。"),
            "failed",
            "缺少工单编号",
        ),
    ],
)
def test_ticket_failure_never_claims_success_and_keeps_pending_action(
    session: Session,
    tool_result: ToolResult,
    expected_status: str,
    answer_fragment: str,
) -> None:
    runtime = runtime_with_pending_ticket(session, f"failure-{tool_result.error_code}")
    stub = StubTicketTools([tool_result])
    runtime.ticket_tools = stub  # type: ignore[assignment]

    result = runtime.invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": f"failure-{tool_result.error_code}",
            "message": "确认",
            "confirmed": True,
        }
    )

    assert result["tool_result"]["status"] == expected_status
    assert result["pending_action"]["type"] == "create_ticket"
    assert result["pending_action"]["device_id"] == "device-from-pending"
    assert stub.calls[0]["device_id"] == "device-from-pending"
    assert answer_fragment in result["answer"]
    assert "工单已创建" not in result["answer"]
    assert "None" not in result["answer"]


def test_ticket_can_retry_after_failure_with_same_idempotency_key(session: Session) -> None:
    thread_id = "failure-then-retry"
    runtime = runtime_with_pending_ticket(session, thread_id)
    stub = StubTicketTools(
        [
            ToolResult(
                status="failed",
                error_code="BUSINESS_HTTP_500",
                message_for_model="业务服务内部错误。",
            ),
            ToolResult(
                status="success",
                data={"ticket_id": "ticket-after-retry", "deduplicated": True},
                message_for_model="已返回同一幂等请求创建的工单。",
            ),
        ]
    )
    runtime.ticket_tools = stub  # type: ignore[assignment]

    failed = runtime.invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": thread_id,
            "message": "确认",
            "confirmed": True,
        }
    )
    retried = runtime.invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": thread_id,
            "message": "再次确认",
            "confirmed": True,
        }
    )

    assert failed["pending_action"]["type"] == "create_ticket"
    assert retried["tool_result"]["status"] == "success"
    assert retried["tool_result"]["data"]["ticket_id"] == "ticket-after-retry"
    assert retried["pending_action"] == {}
    assert stub.calls[0]["idempotency_key"] == stub.calls[1]["idempotency_key"]
