from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from redis import Redis
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.models import Job

QUEUE_KEY = "aftersales:jobs"


def _notify(job_id: str) -> None:
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=0.25)
        client.lpush(QUEUE_KEY, job_id)
        client.close()
    except Exception:
        # PostgreSQL remains the source of truth; Redis only reduces polling latency.
        return


def enqueue_job(
    session: Session,
    *,
    tenant_id: str,
    kind: str,
    payload: dict[str, Any],
    max_attempts: int = 3,
) -> Job:
    job = Job(
        tenant_id=tenant_id,
        kind=kind,
        payload=payload,
        max_attempts=max_attempts,
        status="queued",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    _notify(job.id)
    return job


def claim_job(session: Session, worker_id: str) -> Job | None:
    now = datetime.now(UTC)
    session.execute(
        update(Job)
        .where(
            Job.status == "running",
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
            Job.attempts < Job.max_attempts,
        )
        .values(status="queued", lease_owner=None, lease_expires_at=None)
    )
    session.execute(
        update(Job)
        .where(
            Job.status == "running",
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at < now,
            Job.attempts >= Job.max_attempts,
        )
        .values(status="dead_letter", completed_at=now, error="worker lease expired")
    )
    query = (
        select(Job)
        .where(
            Job.status == "queued",
            Job.available_at <= now,
            or_(Job.lease_expires_at.is_(None), Job.lease_expires_at < now),
        )
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job = session.scalar(query)
    if not job:
        session.commit()
        return None
    job.status = "running"
    job.attempts += 1
    job.lease_owner = worker_id
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=settings.job_lease_seconds)
    session.commit()
    session.refresh(job)
    return job


def heartbeat(session: Session, job: Job, progress: float) -> None:
    now = datetime.now(UTC)
    job.progress = min(max(progress, 0.0), 1.0)
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=settings.job_lease_seconds)
    session.commit()


def complete_job(session: Session, job: Job, result: dict[str, Any]) -> None:
    job.status = "completed"
    job.progress = 1.0
    job.result = result
    job.error = None
    job.completed_at = datetime.now(UTC)
    job.lease_owner = None
    job.lease_expires_at = None
    session.commit()


def fail_job(session: Session, job: Job, error: Exception) -> None:
    now = datetime.now(UTC)
    job.error = str(error)[:4000]
    job.lease_owner = None
    job.lease_expires_at = None
    if job.attempts >= job.max_attempts:
        job.status = "dead_letter"
        job.completed_at = now
    else:
        job.status = "queued"
        job.available_at = now + timedelta(seconds=min(60, 2**job.attempts))
        _notify(job.id)
    session.commit()
