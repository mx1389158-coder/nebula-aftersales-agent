from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from apps.api.app.core.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_schema() -> None:
    from apps.api.app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_compatibility_columns()


def _apply_compatibility_columns() -> None:
    """Add columns introduced after the MVP without destroying local data volumes."""
    additions = {
        "users": [("auto_memory_enabled", "BOOLEAN NOT NULL DEFAULT FALSE")],
        "conversations": [("summary", "TEXT NOT NULL DEFAULT ''")],
        "memories": [("supersedes_id", "VARCHAR(36)")],
        "skills": [
            ("rollout_percent", "INTEGER NOT NULL DEFAULT 100"),
            ("success_count", "INTEGER NOT NULL DEFAULT 0"),
            ("failure_count", "INTEGER NOT NULL DEFAULT 0"),
        ],
        "skill_versions": [
            ("constraints", "JSON NOT NULL DEFAULT '{}'"),
            ("test_report", "JSON NOT NULL DEFAULT '{}'"),
        ],
        "eval_runs": [("tenant_id", "VARCHAR(64) NOT NULL DEFAULT 'demo'")],
    }
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table, columns in additions.items():
            if table not in existing_tables:
                continue
            existing_columns = {item["name"] for item in inspector.get_columns(table)}
            for name, definition in columns:
                if name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
