"""conversation summary for bounded context recovery

Revision ID: 20261104_conversation_summary
Revises: 20261024_password_auth
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261104_conversation_summary"
down_revision: str | Sequence[str] | None = "20261024_password_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("summary", sa.Text(), server_default="", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("conversations", "summary")
