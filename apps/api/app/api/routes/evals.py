from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.database import get_db
from apps.api.app.core.security import require_admin
from apps.api.app.models import EvalRun
from apps.api.app.schemas import EvalRunRequest, ExperimentMatrixRequest, Principal
from apps.api.app.services.jobs import enqueue_job

router = APIRouter()


@router.get("")
def list_runs(
    principal: Principal = Depends(require_admin), session: Session = Depends(get_db)
) -> list[dict]:
    runs = session.scalars(
        select(EvalRun)
        .where(EvalRun.tenant_id == principal.tenant_id)
        .order_by(EvalRun.created_at.desc())
        .limit(30)
    )
    return [
        {
            "id": item.id,
            "dataset_version": item.dataset_version,
            "status": item.status,
            "metrics": item.metrics,
            "created_at": item.created_at,
            "completed_at": item.completed_at,
        }
        for item in runs
    ]


@router.post("/run", status_code=202)
def create_run(
    payload: EvalRunRequest,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    config_hash = hashlib.sha256(
        json.dumps(payload.model_dump(), sort_keys=True).encode("utf-8")
    ).hexdigest()
    run = EvalRun(
        tenant_id=principal.tenant_id,
        dataset_version=payload.dataset_version,
        config_hash=config_hash,
        status="queued",
        metrics={
            "retrieval_variant": payload.retrieval_variant,
            "memory_variant": payload.memory_variant,
            "skill_variant": payload.skill_variant,
        },
    )
    session.add(run)
    session.flush()
    job = enqueue_job(
        session,
        tenant_id=principal.tenant_id,
        kind="evaluation",
        payload={"eval_run_id": run.id},
    )
    return {"run_id": run.id, "job_id": job.id, "status": run.status}


@router.post("/matrix", status_code=202)
def create_experiment_matrix(
    payload: ExperimentMatrixRequest,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, list[str]]:
    # R2/M3 is shared by the retrieval and memory matrices.
    variants = [
        ("no_retrieval", "M3"),
        ("dense", "M3"),
        ("hybrid", "M3"),
        ("hybrid_rerank", "M3"),
        ("lightrag", "M3"),
        ("openviking", "M3"),
        ("hybrid", "M0"),
        ("hybrid", "M1"),
        ("hybrid", "M2"),
    ]
    run_ids: list[str] = []
    job_ids: list[str] = []
    for retrieval_variant, memory_variant in variants:
        config = {
            "dataset_version": payload.dataset_version,
            "retrieval_variant": retrieval_variant,
            "memory_variant": memory_variant,
            "skill_variant": "reviewed",
        }
        run = EvalRun(
            tenant_id=principal.tenant_id,
            dataset_version=payload.dataset_version,
            config_hash=hashlib.sha256(
                json.dumps(config, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            status="queued",
            metrics={
                "retrieval_variant": retrieval_variant,
                "memory_variant": memory_variant,
                "skill_variant": "reviewed",
            },
        )
        session.add(run)
        session.flush()
        job = enqueue_job(
            session,
            tenant_id=principal.tenant_id,
            kind="evaluation",
            payload={"eval_run_id": run.id},
        )
        run_ids.append(run.id)
        job_ids.append(job.id)
    return {"run_ids": run_ids, "job_ids": job_ids}


@router.post("/skill-matrix", status_code=202)
def create_skill_matrix(
    payload: ExperimentMatrixRequest,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_db),
) -> dict[str, list[str]]:
    del payload
    run_ids: list[str] = []
    job_ids: list[str] = []
    for skill_variant in ("none", "manual", "extracted"):
        config = {
            "dataset_version": "aftersales-skill-v1",
            "retrieval_variant": "hybrid",
            "memory_variant": "M3",
            "skill_variant": skill_variant,
        }
        run = EvalRun(
            tenant_id=principal.tenant_id,
            dataset_version="aftersales-skill-v1",
            config_hash=hashlib.sha256(
                json.dumps(config, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            status="queued",
            metrics=config,
        )
        session.add(run)
        session.flush()
        job = enqueue_job(
            session,
            tenant_id=principal.tenant_id,
            kind="evaluation",
            payload={"eval_run_id": run.id},
        )
        run_ids.append(run.id)
        job_ids.append(job.id)
    return {"run_ids": run_ids, "job_ids": job_ids}
