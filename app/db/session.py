from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from ..config import DATA_DIR, DATABASE_URL
from .models import Base


DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_analytics_schema(engine)


def _ensure_analytics_schema(target_engine) -> None:
    inspector = inspect(target_engine)
    if "analytics_operations" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("analytics_operations")}
    if "external_event_id" not in columns:
        try:
            with target_engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE analytics_operations "
                        "ADD COLUMN external_event_id VARCHAR(80)"
                    )
                )
        except OperationalError:
            # Multiple app variants can perform the first startup together.
            refreshed_columns = {
                column["name"]
                for column in inspect(target_engine).get_columns("analytics_operations")
            }
            if "external_event_id" not in refreshed_columns:
                raise
    with target_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_analytics_operations_external_event_id "
                "ON analytics_operations (external_event_id)"
            )
        )


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
