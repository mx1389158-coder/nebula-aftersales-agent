from __future__ import annotations

import hashlib
import json
import math
import platform
import socket
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.core.config import PROJECT_ROOT, settings
from apps.api.app.core.database import SessionLocal, create_schema
from apps.api.app.models import EvalRun, Job, Memory
from apps.api.app.services.documents import DocumentIngestor
from apps.api.app.services.jobs import QUEUE_KEY, claim_job, complete_job, fail_job, heartbeat
from packages.agent_core import AgentRuntime

WORKER_ID = f"{socket.gethostname()}-{id(object())}"


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "uncommitted"


def _prepare_evaluation_memories(
    session: Session, cases: list[dict[str, Any]], *, tenant_id: str, user_id: str
) -> None:
    for case in cases:
        setup = case.get("memory_setup")
        if not setup:
            continue
        current_fact = str(setup["current"])
        existing = session.scalar(
            select(Memory).where(
                Memory.tenant_id == tenant_id,
                Memory.user_id == user_id,
                Memory.fact == current_fact,
            )
        )
        if existing:
            continue
        old = Memory(
            tenant_id=tenant_id,
            user_id=user_id,
            kind="preference",
            fact=str(setup["old"]),
            confidence=0.95,
            consent=True,
            valid_to=datetime.now(UTC) - timedelta(days=1),
        )
        session.add(old)
        session.flush()
        session.add(
            Memory(
                tenant_id=tenant_id,
                user_id=user_id,
                kind="preference",
                fact=current_fact,
                confidence=1.0,
                consent=True,
                supersedes_id=old.id,
            )
        )
    session.commit()


def _process_document(session: Session, job: Job) -> dict[str, Any]:
    payload = job.payload
    root = Path(settings.job_data_dir).resolve()
    source = Path(str(payload["file_path"])).resolve()
    if root not in source.parents:
        raise ValueError("任务文件不在允许的工作目录中")
    if not source.is_file():
        raise ValueError("待处理文档文件不存在")
    heartbeat(session, job, 0.1)
    document = DocumentIngestor(session).ingest(
        tenant_id=job.tenant_id,
        filename=str(payload["filename"]),
        content=source.read_bytes(),
        product_id=str(payload["product_id"]),
        model=payload.get("model"),
        firmware_version=payload.get("firmware_version"),
        doc_version=str(payload["doc_version"]),
        title=payload.get("title"),
    )
    heartbeat(session, job, 0.9)
    return {"document_id": document.id, "chunk_count": len(document.chunks)}


def _evaluate(session: Session, job: Job) -> dict[str, Any]:
    run = session.scalar(
        select(EvalRun).where(
            EvalRun.id == job.payload.get("eval_run_id"), EvalRun.tenant_id == job.tenant_id
        )
    )
    if not run:
        raise ValueError("评测运行不存在")
    run.status = "running"
    session.commit()
    fixture = PROJECT_ROOT / "evals" / "datasets" / f"{run.dataset_version}.jsonl"
    if not fixture.exists():
        raise ValueError(f"dataset not found: {fixture.name}")
    cases = [
        json.loads(line)
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    evaluation_user_id = "00000000-0000-0000-0000-000000000001"
    _prepare_evaluation_memories(
        session, cases, tenant_id=job.tenant_id, user_id=evaluation_user_id
    )
    runtime = AgentRuntime(session)
    correct = cited = refused_correctly = decision_correct = 0
    retrieval_cases = retrieval_hits = relevant_retrieved = total_retrieved = 0
    reciprocal_rank = ndcg = 0.0
    safety_total = safety_failures = tool_total = tool_correct = 0
    latencies: list[float] = []
    badcases: list[dict[str, Any]] = []
    category_totals: Counter[str] = Counter()
    category_correct: Counter[str] = Counter()
    category_latencies: defaultdict[str, list[float]] = defaultdict(list)
    skill_hits = 0
    skill_steps = 0
    for index, case in enumerate(cases):
        started = time.perf_counter()
        result = runtime.invoke(
            {
                "tenant_id": job.tenant_id,
                "user_id": evaluation_user_id,
                "message": case["question"],
                "retrieval_variant": run.metrics.get("retrieval_variant", "hybrid"),
                "memory_variant": run.metrics.get("memory_variant", "M3"),
                "skill_variant": run.metrics.get("skill_variant", "reviewed"),
                "evaluation_mode": True,
                **case.get("context", {}),
            }
        )
        latencies.append((time.perf_counter() - started) * 1000)
        answer = result.get("answer", "")
        skills = result.get("skills", [])
        skill_hits += int(bool(skills))
        skill_steps += sum(len(item.get("steps", [])) for item in skills)
        keywords = case.get("expected_keywords", [])
        forbidden_keywords = case.get("forbidden_keywords", [])
        decision_ok = result.get("decision") == case.get("expected_decision", "ANSWER")
        decision_correct += int(decision_ok)
        answer_ok = all(keyword in answer for keyword in keywords) and not any(
            keyword in answer for keyword in forbidden_keywords
        )
        evidence_versions_ok = not any(
            version in item.title
            for version in case.get("forbidden_versions", [])
            for item in result.get("evidence", [])
        )
        category = str(case.get("category", "unknown"))
        category_totals[category] += 1
        category_latencies[category].append(latencies[-1])
        if answer_ok and decision_ok and evidence_versions_ok:
            correct += 1
            category_correct[category] += 1
        else:
            badcases.append(
                {
                    "id": case["id"],
                    "category": category,
                    "decision": result.get("decision"),
                    "answer": answer,
                    "answer_ok": answer_ok,
                    "evidence_versions_ok": evidence_versions_ok,
                }
            )
        cited += int(bool(result.get("evidence")))
        refused_correctly += int(case.get("expected_decision") == "REFUSE" and decision_ok)
        if category == "safety_handoff":
            safety_total += 1
            safety_failures += int(result.get("decision") != "ESCALATE")
        if category == "tool_confirmation":
            tool_total += 1
            tool_correct += int(decision_ok)
        context = case.get("context", {})
        expected_model = context.get("model")
        if expected_model:
            retrieval_cases += 1
            evidence = result.get("evidence", [])
            relevance = [
                expected_model in item.title
                and (
                    not context.get("firmware_version") or context["firmware_version"] in item.title
                )
                for item in evidence
            ]
            relevant_retrieved += sum(relevance)
            total_retrieved += len(relevance)
            if any(relevance):
                retrieval_hits += 1
                rank = relevance.index(True) + 1
                reciprocal_rank += 1 / rank
                ndcg += 1 / math.log2(rank + 1)
        if index % 10 == 0:
            heartbeat(session, job, (index + 1) / max(len(cases), 1))
    total = len(cases) or 1
    ordered = sorted(latencies)
    p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95)) if ordered else 0
    metrics = {
        **run.metrics,
        "total": len(cases),
        "task_success": round(correct / total, 4),
        "decision_accuracy": round(decision_correct / total, 4),
        "citation_rate": round(cited / total, 4),
        "citation_precision": round(relevant_retrieved / max(total_retrieved, 1), 4),
        "retrieval_recall_at_k": round(retrieval_hits / max(retrieval_cases, 1), 4),
        "mrr": round(reciprocal_rank / max(retrieval_cases, 1), 4),
        "ndcg_at_k": round(ndcg / max(retrieval_cases, 1), 4),
        "tool_accuracy": round(tool_correct / max(tool_total, 1), 4),
        "dangerous_action_rate": round(safety_failures / max(safety_total, 1), 4),
        "refusal_correct": refused_correctly,
        "p95_ms": round(ordered[p95_index], 2) if ordered else 0,
        "badcases": badcases[:100],
        "category_metrics": {
            category: {
                "total": count,
                "task_success": round(category_correct[category] / max(count, 1), 4),
                "p95_ms": round(
                    sorted(category_latencies[category])[
                        min(
                            len(category_latencies[category]) - 1,
                            int(len(category_latencies[category]) * 0.95),
                        )
                    ],
                    2,
                ),
            }
            for category, count in sorted(category_totals.items())
        },
        "dataset_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "git_commit": _git_commit(),
        "seed": 42,
        "hardware": platform.platform(),
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "model": settings.ollama_model if settings.llm_provider == "ollama" else "template-v1",
        "prompt_version": "answer-v2-explicit-troubleshooting",
        "skill_hit_rate": round(skill_hits / total, 4),
        "average_skill_steps": round(skill_steps / total, 4),
    }
    run.metrics = metrics
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    session.commit()
    report_path = Path(settings.job_data_dir).resolve() / f"eval-{run.id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps({"metrics": metrics, "badcases": badcases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"eval_run_id": run.id, "metrics": metrics, "report_path": str(report_path)}


def _expire_memories(session: Session, job: Job) -> dict[str, Any]:
    now = datetime.now(UTC)
    memories = list(
        session.scalars(
            select(Memory).where(
                Memory.tenant_id == job.tenant_id,
                Memory.status == "active",
                Memory.valid_to.is_not(None),
                Memory.valid_to <= now,
            )
        )
    )
    for memory in memories:
        memory.status = "expired"
    session.commit()
    return {"expired": len(memories)}


PROCESSORS = {
    "document_ingest": _process_document,
    "evaluation": _evaluate,
    "memory_expiry": _expire_memories,
}


def process_once() -> bool:
    with SessionLocal() as session:
        job = claim_job(session, WORKER_ID)
        if not job:
            return False
        try:
            processor = PROCESSORS.get(job.kind)
            if not processor:
                raise ValueError(f"unsupported job kind: {job.kind}")
            complete_job(session, job, processor(session, job))
        except Exception as exc:
            session.rollback()
            fresh = session.get(Job, job.id)
            if fresh:
                if job.kind == "evaluation":
                    run = session.get(EvalRun, job.payload.get("eval_run_id"))
                    if run and job.attempts >= job.max_attempts:
                        run.status = "failed"
                        run.completed_at = datetime.now(UTC)
                fail_job(session, fresh, exc)
        return True


def run_forever() -> None:
    create_schema()
    redis_client: Redis | None
    try:
        redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
        redis_client.ping()
    except Exception:
        redis_client = None
    while True:
        if process_once():
            continue
        if redis_client:
            try:
                redis_client.brpop([QUEUE_KEY], timeout=2)
                continue
            except Exception:
                redis_client = None
        time.sleep(2)


if __name__ == "__main__":
    run_forever()
