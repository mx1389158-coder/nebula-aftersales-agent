from __future__ import annotations

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from apps.api.app.core.database import Base
from apps.api.app.models import Device, User
from apps.api.app.services.seed import seed_demo


def test_seed_inserts_user_before_device_foreign_key() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_demo(session)

        device = session.scalar(select(Device))
        assert device is not None
        assert session.get(User, device.user_id) is not None
