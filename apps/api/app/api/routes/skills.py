from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import require_admin
from apps.api.app.models import AuditLog, Skill, SkillVersion
from apps.api.app.schemas import (
    Principal,
    RolloutRequest,
    SkillCreate,
    SkillVersionCreate,
)
from apps.api.app.services.skills import validate_skill

router = APIRouter()


@router.get("")
def list_skills(
    principal: Principal = Depends(require_admin), session: Session = Depends(get_db)
) -> list[dict]:
    rows = session.scalars(
        select(Skill)
        .where(Skill.tenant_id == principal.tenant_id)
        .order_by(Skill.updated_at.desc())
    )
    return [
        {
            "id": item.id,
            "name": item.name,
            "scope": item.scope,
            "status": item.status,
            "active_version": item.active_version,
            "rollout_percent": item.rollout_percent,
            "success_count": item.success_count,
            "failure_count": item.failure_count,
        }
        for item in rows
    ]


@router.post("", status_code=201)
def create_skill(
    payload: SkillCreate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    skill = Skill(tenant_id=principal.tenant_id, name=payload.name, scope=payload.scope)
    session.add(skill)
    session.flush()
    report = validate_skill(payload.steps, payload.tests, payload.constraints)
    version = SkillVersion(
        skill_id=skill.id,
        version=1,
        steps=payload.steps,
        tests=payload.tests,
        constraints=payload.constraints,
        test_report=report,
    )
    session.add(version)
    session.commit()
    return {"id": skill.id, "status": skill.status, "version": version.version}


@router.post("/{skill_id}/versions", status_code=201)
def create_version(
    skill_id: str,
    payload: SkillVersionCreate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    skill = session.scalar(
        select(Skill).where(Skill.id == skill_id, Skill.tenant_id == principal.tenant_id)
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    latest = (
        session.scalar(
            select(func.max(SkillVersion.version)).where(SkillVersion.skill_id == skill.id)
        )
        or 0
    )
    report = validate_skill(payload.steps, payload.tests, payload.constraints)
    version = SkillVersion(
        skill_id=skill.id,
        version=latest + 1,
        steps=payload.steps,
        tests=payload.tests,
        constraints=payload.constraints,
        test_report=report,
    )
    skill.status = "candidate"
    session.add(version)
    session.commit()
    return {"id": skill.id, "version": version.version, "test_report": report}


@router.post("/{skill_id}/approve")
def approve_skill(
    skill_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    skill = session.scalar(
        select(Skill).where(Skill.id == skill_id, Skill.tenant_id == principal.tenant_id)
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    latest = session.scalar(
        select(func.max(SkillVersion.version)).where(SkillVersion.skill_id == skill.id)
    )
    version = session.scalar(
        select(SkillVersion).where(
            SkillVersion.skill_id == skill.id, SkillVersion.version == latest
        )
    )
    if not version or not version.test_report.get("passed"):
        raise HTTPException(status_code=409, detail="静态检查和回归测试通过后才能发布")
    version.approved_by = principal.user_id
    skill.active_version = version.version
    skill.status = "active"
    session.add(
        AuditLog(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="skill.approve",
            entity_type="skill",
            entity_id=skill.id,
            detail={"version": version.version},
        )
    )
    session.commit()
    return {"id": skill.id, "status": skill.status, "active_version": skill.active_version}


@router.post("/{skill_id}/rollback/{version_number}")
def rollback_skill(
    skill_id: str,
    version_number: int,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    skill = session.scalar(
        select(Skill).where(Skill.id == skill_id, Skill.tenant_id == principal.tenant_id)
    )
    version = session.scalar(
        select(SkillVersion).where(
            SkillVersion.skill_id == skill_id, SkillVersion.version == version_number
        )
    )
    if not skill or not version:
        raise HTTPException(status_code=404, detail="技能或版本不存在")
    skill.active_version = version_number
    skill.status = "active"
    session.add(
        AuditLog(
            tenant_id=principal.tenant_id,
            actor_id=principal.user_id,
            action="skill.rollback",
            entity_type="skill",
            entity_id=skill.id,
            detail={"version": version_number},
        )
    )
    session.commit()
    return {"id": skill.id, "status": skill.status, "active_version": version_number}


@router.patch("/{skill_id}/rollout")
def set_rollout(
    skill_id: str,
    payload: RolloutRequest,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    skill = session.scalar(
        select(Skill).where(Skill.id == skill_id, Skill.tenant_id == principal.tenant_id)
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    skill.rollout_percent = payload.percent
    session.commit()
    return {"id": skill.id, "rollout_percent": skill.rollout_percent}


@router.post("/{skill_id}/deactivate")
def deactivate_skill(
    skill_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict:
    skill = session.scalar(
        select(Skill).where(Skill.id == skill_id, Skill.tenant_id == principal.tenant_id)
    )
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    skill.status = "inactive"
    session.commit()
    return {"id": skill.id, "status": skill.status}
