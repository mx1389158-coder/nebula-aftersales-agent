from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from apps.api.app.models import Job, Memory
from apps.api.app.services.jobs import claim_job, enqueue_job, fail_job
from apps.api.app.services.skills import validate_skill
from packages.agent_core.providers import EvidenceTemplateProvider
from packages.agent_core.runtime import AgentRuntime
from packages.context.memory import GovernedMemoryStore


def test_agent_persists_confirmation_and_executes_ticket(session: Session) -> None:
    runtime = AgentRuntime(session, EvidenceTemplateProvider())
    first = runtime.invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "confirm-thread",
            "message": "请创建工单处理无法联网",
            "contact": "user@example.invalid",
        }
    )
    assert first["decision"] == "TOOL"
    assert first["pending_action"]["type"] == "create_ticket"
    second = runtime.invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "confirm-thread",
            "message": "确认",
            "confirmed": True,
        }
    )
    assert second["decision"] == "TOOL"
    assert second["tool_result"]["status"] == "success"
    assert second["pending_action"] == {}


def test_agent_escalates_high_risk_request(session: Session) -> None:
    result = AgentRuntime(session, EvidenceTemplateProvider()).invoke(
        {
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "thread_id": "danger-thread",
            "message": "设备冒烟并且有烧焦味，我能拆机吗？",
        }
    )
    assert result["decision"] == "ESCALATE"
    assert result["handoff_id"]
    assert "断电" in result["answer"]


def test_memory_update_reuses_sensitive_data_guard(session: Session) -> None:
    store = GovernedMemoryStore(session)
    memory = store.add(tenant_id="tenant-1", user_id="user-1", fact="偏好中文说明")
    try:
        store.update(memory, actor_id="user-1", changes={"fact": "验证码 123456"})
    except ValueError as exc:
        assert "禁止写入" in str(exc)
    else:
        raise AssertionError("sensitive memory update must be rejected")
    stored = session.get(Memory, memory.id)
    assert stored and stored.fact == "偏好中文说明"


def test_job_retries_then_enters_dead_letter(session: Session) -> None:
    job = enqueue_job(session, tenant_id="tenant-1", kind="unknown", payload={}, max_attempts=2)
    first = claim_job(session, "worker-1")
    assert first and first.id == job.id
    fail_job(session, first, RuntimeError("first"))
    first.available_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    second = claim_job(session, "worker-1")
    assert second
    fail_job(session, second, RuntimeError("second"))
    stored = session.get(Job, job.id)
    assert stored and stored.status == "dead_letter"
    assert stored.attempts == 2


def test_skill_static_gate_blocks_unapproved_tools() -> None:
    report = validate_skill(
        [{"tool": "shell", "action": "执行任意命令"}],
        [{"input": "测试", "expected_decision": "TOOL"}],
        {"max_steps": 3},
    )
    assert report["passed"] is False
    assert report["static_checks"]["errors"]
