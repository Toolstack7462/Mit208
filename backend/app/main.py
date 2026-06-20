"""PhishGuard FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import Base, engine
from .routers import audit, auth, dashboard, emails, requests


def _database_connected() -> bool:
    """Return True if a simple query against the configured database succeeds."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they do not yet exist (idempotent; safe alongside schema.sql).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="PhishGuard API",
    description=(
        "PhishGuard — phishing email detection and quarantine management API.\n\n"
        "Rule-based risk scoring with JWT-secured analyst and staff workflows."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["health"])
def root():
    return {"name": "PhishGuard API", "version": "1.0.0", "docs": "/docs", "status": "ok"}


@app.get("/api/health", tags=["health"])
def health_api():
    return {"status": "ok"}


@app.get("/health", tags=["system"])
def health():
    """Application status plus live database-connectivity check."""
    connected = _database_connected()
    return {
        "status": "ok" if connected else "degraded",
        "app": "PhishGuard API",
        "version": "1.0.0",
        "database_connected": connected,
    }


@app.get("/system/database-status", tags=["system"])
def database_status():
    """Report which database engine is in use (PostgreSQL vs SQLite fallback)."""
    dialect = engine.dialect.name  # "postgresql" | "sqlite"
    is_sqlite = dialect == "sqlite"
    return {
        "engine": dialect,
        "type": "SQLite (local fallback)" if is_sqlite else "PostgreSQL",
        "using_fallback": is_sqlite,
        "official_target": "PostgreSQL",
        "connected": _database_connected(),
        # URL scheme only — credentials are never exposed.
        "url_scheme": settings.database_url.split("://", 1)[0],
    }


app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(requests.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
