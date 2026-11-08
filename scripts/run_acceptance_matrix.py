"""Run the reproducible local acceptance matrix and write a compact report."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select

from apps.api.app.api.routes.evals import create_run
from apps.api.app.core.config import settings
from apps.api.app.core.database import SessionLocal
from apps.api.app.models import EvalRun, Job
from apps.api.app.schemas import EvalRunRequest, Principal
from apps.worker.app.main import process_once

PRINCIPAL = Principal(
    user_id="00000000-0000-0000-0000-000000000001",
    tenant_id="demo",
    role="admin",
)


def enqueue(configs: list[dict[str, str]]) -> list[dict[str, str]]:
    created: list[dict[str, str]] = []
    with SessionLocal() as session:
        for config in configs:
            response = create_run(EvalRunRequest(**config), PRINCIPAL, session)
            created.append({**config, **response})
    return created


def wait_for_jobs(created: list[dict[str, str]], timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    job_ids = {item["job_id"] for item in created}
    while time.monotonic() < deadline:
        with SessionLocal() as session:
            statuses = dict(
                session.execute(select(Job.id, Job.status).where(Job.id.in_(job_ids))).all()
            )
        if statuses and all(
            value in {"completed", "failed", "dead_letter"} for value in statuses.values()
        ):
            return
        if not process_once():
            time.sleep(0.25)
    raise TimeoutError("acceptance matrix did not finish before timeout")


def collect(created: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with SessionLocal() as session:
        for item in created:
            run = session.get(EvalRun, item["run_id"])
            job = session.get(Job, item["job_id"])
            rows.append(
                {
                    "run_id": item["run_id"],
                    "dataset_version": item["dataset_version"],
                    "retrieval_variant": item["retrieval_variant"],
                    "memory_variant": item["memory_variant"],
                    "skill_variant": item["skill_variant"],
                    "status": run.status if run else "missing",
                    "job_status": job.status if job else "missing",
                    "metrics": run.metrics if run else {},
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument(
        "--production-only",
        action="store_true",
        help="run only the default hybrid/M3/reviewed production configuration",
    )
    args = parser.parse_args()

    core = [
        ("no_retrieval", "M3"),
        ("dense", "M3"),
        ("hybrid", "M3"),
        ("hybrid_rerank", "M3"),
        ("hybrid", "M0"),
        ("hybrid", "M1"),
        ("hybrid", "M2"),
    ]
    if args.production_only:
        core = [("hybrid", "M3")]
    unavailable: list[dict[str, str]] = []
    for variant, url in (
        ("lightrag", settings.lightrag_base_url),
        ("openviking", settings.openviking_base_url),
    ):
        if args.include_external and url:
            core.append((variant, "M3"))
        else:
            unavailable.append(
                {"retrieval_variant": variant, "reason": "external service URL is not configured"}
            )
    configs = [
        {
            "dataset_version": "aftersales-smoke-v1",
            "retrieval_variant": retrieval,
            "memory_variant": memory,
            "skill_variant": "reviewed",
        }
        for retrieval, memory in core
    ]
    if not args.production_only:
        configs.extend(
            {
                "dataset_version": "aftersales-skill-v1",
                "retrieval_variant": "hybrid",
                "memory_variant": "M3",
                "skill_variant": skill,
            }
            for skill in ("none", "manual", "extracted")
        )
    created = enqueue(configs)
    wait_for_jobs(created, args.timeout)
    report = {
        "runs": collect(created),
        "unavailable_external_baselines": unavailable,
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
    }
    output = Path(settings.job_data_dir) / "acceptance-matrix.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
