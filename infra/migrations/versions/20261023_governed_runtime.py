"""governed runtime, reliable jobs and feedback

Revision ID: 20261023_governed_runtime
Revises: bcb92d70dab9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_governed_runtime"
down_revision: str | Sequence[str] | None = "bcb92d70dab9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auto_memory_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("memories", sa.Column("supersedes_id", sa.String(36), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_memories_supersedes_id", "memories", "memories", ["supersedes_id"], ["id"]
        )
    op.add_column(
        "skills", sa.Column("rollout_percent", sa.Integer(), server_default="100", nullable=False)
    )
    op.add_column(
        "skills", sa.Column("success_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "skills", sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "skill_versions", sa.Column("constraints", sa.JSON(), server_default="{}", nullable=False)
    )
    op.add_column(
        "skill_versions", sa.Column("test_report", sa.JSON(), server_default="{}", nullable=False)
    )
    op.add_column(
        "eval_runs", sa.Column("tenant_id", sa.String(64), server_default="demo", nullable=False)
    )
    op.create_index("ix_eval_runs_tenant_id", "eval_runs", ["tenant_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("kind", sa.String(40), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("lease_owner", sa.String(100)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_claim", "jobs", ["status", "available_at", "created_at"])
    op.create_table(
        "agent_checkpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("thread_id", sa.String(80), nullable=False, index=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("pending_action", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "thread_id"),
    )
    op.create_table(
        "human_handoffs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("thread_id", sa.String(80), nullable=False, index=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("assigned_to", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "message_id"),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("human_handoffs")
    op.drop_table("agent_checkpoints")
    op.drop_table("jobs")
    op.drop_index("ix_eval_runs_tenant_id", table_name="eval_runs")
    op.drop_column("eval_runs", "tenant_id")
    op.drop_column("skill_versions", "test_report")
    op.drop_column("skill_versions", "constraints")
    op.drop_column("skills", "failure_count")
    op.drop_column("skills", "success_count")
    op.drop_column("skills", "rollout_percent")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_memories_supersedes_id", "memories", type_="foreignkey")
    op.drop_column("memories", "supersedes_id")
    op.drop_column("users", "auto_memory_enabled")
