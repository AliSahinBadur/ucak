from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from .models import Base


settings = get_settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Routes run as sync defs in Starlette's threadpool, so connections are shared
# across threads and writers must wait out concurrent writes instead of failing
# with "database is locked" at the 5-second default.
engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")  # readers keep working during writes
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# Columns added to tables that already ship in the field. `create_all` only
# creates missing *tables*, and the project carries no migration tool, so a
# workstation whose data/app.db predates these columns would fail every query
# that selects them. Each entry must stay nullable and default-free: the rows
# already on disk have no value to backfill, and readers treat NULL as
# "unknown" rather than inventing one.
_SQLITE_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "documents": {
        "extraction_quality": "JSON",
    },
    "document_pages": {
        "extraction_method": "VARCHAR(32)",
        "ocr_attempted": "BOOLEAN",
        "char_count": "INTEGER",
        "word_count": "INTEGER",
    },
}


def _add_missing_sqlite_columns() -> None:
    with engine.begin() as connection:
        for table_name, columns in _SQLITE_ADDED_COLUMNS.items():
            existing = {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})")
            }
            if not existing:
                continue  # create_all just built it complete, or it is not in use
            for column_name, column_type in columns.items():
                if column_name in existing:
                    continue
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    if _is_sqlite:
        _add_missing_sqlite_columns()


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
