"""SQLAlchemy engine / session setup.

Works with PostgreSQL (default) or SQLite (zero-install fallback). The only
SQLite-specific tweak is the ``check_same_thread`` connect arg.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def session_scope(session_factory):
    """Yield a session that rolls back if the caller raises, then always closes.

    A handler that raises part-way through a multi-row change (email status +
    review + audit entry) must not leave those pending writes attached to the
    session. Rolling back explicitly makes the request atomic: either the commit
    in the handler succeeds, or nothing is written.

    Parameterised by the factory so the test suite can bind the same behaviour to
    its own engine instead of reimplementing it (see tests/conftest.py).
    """
    db = session_factory()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI dependency that yields a request-scoped DB session."""
    yield from session_scope(SessionLocal)
