from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import get_principal, require_admin
from apps.api.app.models import Job
from apps.api.app.schemas import JobView, Principal
from apps.api.app.services.jobs import _notify

router = APIRouter()


@router.get("/{job_id}", response_model=JobView)
def get_job(
    job_id: str,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> Job:
    job = session.scalar(select(Job).where(Job.id == job_id, Job.tenant_id == principal.tenant_id))
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@router.post("/{job_id}/retry", response_model=JobView)
def retry_job(
    job_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> Job:
    job = session.scalar(select(Job).where(Job.id == job_id, Job.tenant_id == principal.tenant_id))
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status not in {"failed", "dead_letter"}:
        raise HTTPException(status_code=409, detail="只有失败任务可以重试")
    job.status = "queued"
    job.attempts = 0
    job.error = None
    job.completed_at = None
    session.commit()
    session.refresh(job)
    _notify(job.id)
    return job
