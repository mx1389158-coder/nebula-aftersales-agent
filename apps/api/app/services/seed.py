from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import PROJECT_ROOT, settings
from apps.api.app.core.security import hash_password
from apps.api.app.models import Device, Document, Skill, SkillVersion, User
from apps.api.app.services.documents import DocumentIngestor


def _seed_bootstrap_admin(session: Session) -> None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    bootstrap = session.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
    if not bootstrap:
        bootstrap = User(
            tenant_id="default",
            email=settings.bootstrap_admin_email,
            display_name="Bootstrap Admin",
            role="admin",
        )
        session.add(bootstrap)
    bootstrap.password_hash = hash_password(settings.bootstrap_admin_password)


def seed_demo(session: Session) -> None:
    _seed_bootstrap_admin(session)
    if not settings.demo_mode:
        session.commit()
        return

    user = session.get(User, "00000000-0000-0000-0000-000000000001")
    if not user:
        user = User(
            id="00000000-0000-0000-0000-000000000001",
            tenant_id="demo",
            email="demo@example.com",
            display_name="演示用户",
            role="admin",
        )
        session.add(user)
        session.flush()
    if not user.password_hash and settings.demo_mode:
        user.password_hash = hash_password("demo-change-me")
    if not session.get(Device, "00000000-0000-0000-0000-000000000101"):
        session.add(
            Device(
                id="00000000-0000-0000-0000-000000000101",
                tenant_id="demo",
                user_id=user.id,
                product_id="router",
                model="X2",
                firmware_version="2.1.0",
                serial_number="DEMO-X2-0001",
            )
        )
    session.commit()
    for origin, name, steps in (
        (
            "manual",
            "人工编写联网排查技能",
            [
                {"instruction": "核对型号和固件版本"},
                {"instruction": "检查电源、线缆和网络状态"},
                {"instruction": "读取错误码并按证据排查"},
                {"instruction": "未恢复时经确认创建工单"},
            ],
        ),
        (
            "extracted",
            "已审核成功轨迹排查技能",
            [
                {"instruction": "复现症状并记录状态灯"},
                {"instruction": "断电三十秒后重启"},
                {"instruction": "导出诊断日志"},
                {"instruction": "依据安全边界决定继续或转人工"},
            ],
        ),
    ):
        existing_skill = session.scalar(
            select(Skill).where(Skill.tenant_id == "demo", Skill.name == name)
        )
        if existing_skill:
            continue
        skill = Skill(
            tenant_id="demo",
            name=name,
            scope={"origin": origin},
            status="active",
            active_version=1,
            rollout_percent=100,
        )
        session.add(skill)
        session.flush()
        session.add(
            SkillVersion(
                skill_id=skill.id,
                version=1,
                steps=steps,
                tests=[{"input": "设备无法联网", "expected_decision": "ANSWER"}],
                constraints={"max_steps": 6, "tool_whitelist": ["search_manual", "create_ticket"]},
                test_report={"passed": True, "seeded_evaluation_baseline": True},
                approved_by="system-seed",
            )
        )
    session.commit()
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "seed_documents.json"
    if not fixture_path.exists():
        return
    records = json.loads(fixture_path.read_text(encoding="utf-8"))
    ingestor = DocumentIngestor(session)
    for record in records:
        existing = session.scalar(
            select(Document.id).where(
                Document.tenant_id == "demo",
                Document.source == record["source"],
                Document.doc_version == record["doc_version"],
            )
        )
        if existing:
            continue
        document = ingestor.ingest(
            tenant_id="demo",
            filename=record["source"],
            content=record["content"].encode("utf-8"),
            product_id=record["product_id"],
            model=record.get("model"),
            firmware_version=record.get("firmware_version"),
            doc_version=record["doc_version"],
            title=record["title"],
        )
        ingestor.publish(document)
