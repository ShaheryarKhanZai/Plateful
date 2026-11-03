"""Database engine and per-request session."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# hide_parameters=True keeps query values (emails, hashes) out of error messages.
_s = get_settings()
# The pool is sized to the 40 worker threads FastAPI uses for normal routes, so a request does not
# sit waiting for a free connection. pool_timeout makes an overloaded instance fail fast.
engine = create_engine(_s.database_url, pool_pre_ping=True, hide_parameters=True,
                       pool_size=_s.db_pool_size, max_overflow=_s.db_max_overflow,
                       pool_timeout=_s.db_pool_timeout)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
