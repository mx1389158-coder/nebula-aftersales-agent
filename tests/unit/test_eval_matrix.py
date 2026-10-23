from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.api.routes.evals import create_experiment_matrix, create_skill_matrix
from apps.api.app.models import EvalRun
from apps.api.app.schemas import ExperimentMatrixRequest, Principal


def test_experiment_matrix_matches_plan(session: Session) -> None:
    result = create_experiment_matrix(
        ExperimentMatrixRequest(dataset_version="aftersales-smoke-v1"),
        Principal(user_id="user-1", tenant_id="tenant-1", role="admin"),
        session,
    )
    assert len(result["run_ids"]) == 9
    runs = list(session.scalars(select(EvalRun).where(EvalRun.id.in_(result["run_ids"]))))
    variants = {(run.metrics["retrieval_variant"], run.metrics["memory_variant"]) for run in runs}
    assert ("no_retrieval", "M3") in variants
    assert ("lightrag", "M3") in variants
    assert ("openviking", "M3") in variants
    assert ("hybrid", "M0") in variants


def test_skill_matrix_has_three_baselines(session: Session) -> None:
    result = create_skill_matrix(
        ExperimentMatrixRequest(),
        Principal(user_id="user-1", tenant_id="tenant-1", role="admin"),
        session,
    )
    runs = list(session.scalars(select(EvalRun).where(EvalRun.id.in_(result["run_ids"]))))
    assert {run.metrics["skill_variant"] for run in runs} == {
        "none",
        "manual",
        "extracted",
    }
