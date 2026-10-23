from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.api.app.models import Memory
from packages.context.memory import GovernedMemoryStore


def test_memory_rejects_sensitive_content(session: Session) -> None:
    store = GovernedMemoryStore(session)
    with pytest.raises(ValueError, match="禁止写入"):
        store.add(tenant_id="tenant-1", user_id="user-1", fact="验证码 123456", consent=True)


def test_memory_is_strictly_user_scoped(session: Session) -> None:
    store = GovernedMemoryStore(session)
    store.add(tenant_id="tenant-1", user_id="user-1", fact="我的设备型号是 X2")
    assert len(store.search("设备型号", tenant_id="tenant-1", user_id="user-1")) == 1
    assert store.search("设备型号", tenant_id="tenant-1", user_id="user-2") == []


def test_governed_memory_excludes_expired_and_superseded(session: Session) -> None:
    old = Memory(
        tenant_id="tenant-1",
        user_id="user-1",
        kind="preference",
        fact="过期偏好-M001",
        consent=True,
        valid_to=datetime.now(UTC) - timedelta(days=1),
    )
    session.add(old)
    session.flush()
    session.add(
        Memory(
            tenant_id="tenant-1",
            user_id="user-1",
            kind="preference",
            fact="当前偏好-M001",
            consent=True,
            supersedes_id=old.id,
        )
    )
    session.commit()
    store = GovernedMemoryStore(session)
    governed = store.search("M001", tenant_id="tenant-1", user_id="user-1", governed=True)
    raw = store.search("M001", tenant_id="tenant-1", user_id="user-1", governed=False)
    assert [item.fact for item in governed] == ["当前偏好-M001"]
    assert {item.fact for item in raw} == {"当前偏好-M001", "过期偏好-M001"}
