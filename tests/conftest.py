from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.core.database import Base
from apps.api.app.models import User


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as value:
        value.add(
            User(
                id="user-1",
                tenant_id="tenant-1",
                email="user@example.com",
                display_name="测试用户",
            )
        )
        value.add(
            User(
                id="user-2",
                tenant_id="tenant-1",
                email="other@example.com",
                display_name="其他用户",
            )
        )
        value.commit()
        yield value
