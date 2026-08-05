"""PhishGuard FastAPI application entrypoint."""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .database import Base, engine
from .routers import audit, auth, dashboard, emails, requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phishguard")


def _database_connected() -> bool:
    """Return True if a simple query against the configured database succeeds."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they do not yet exist (idempotent; safe alongside schema.sql).
    Base.metadata.create_all(bind=engine)
    if not _database_connected():
        logger.error("Database is not reachable at startup — /health will report 'degraded'.")
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


# --- Consistent error envelope ---------------------------------------------
# Every error the API returns has the same shape:
#   {"error": {"code": <int>, "message": <str>, "details": <any|null>,
#              "request_id": <str>}}
# The frontend reads error.message, so an unexpected server fault produces a
# readable message instead of an empty screen. request_id lets a user-visible
# error be matched to the corresponding server log line.

def _error_body(code: int, message: str, request_id: str, details=None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


@app.middleware("http")
async def add_request_id_and_security_headers(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    # Defensive headers. This API returns JSON only, so a restrictive CSP and
    # nosniff cost nothing and stop a JSON response being rendered as markup.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Wrap deliberate HTTPExceptions (401/403/404/409/422/429) in the envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.status_code, str(exc.detail), _request_id(request)),
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Turn Pydantic validation errors into a readable, field-level message."""
    fields = []
    for err in exc.errors():
        # loc is e.g. ("body", "reason") — drop the "body" prefix.
        location = ".".join(str(p) for p in err["loc"][1:]) or "request"
        fields.append({"field": location, "message": err["msg"]})
    summary = "; ".join(f"{f['field']}: {f['message']}" for f in fields) or "Invalid request"
    return JSONResponse(
        status_code=422,
        content=_error_body(422, summary, _request_id(request), details=fields),
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Database faults become a 503, never a leaked SQL string.

    Constraint violations and connection drops previously surfaced as an opaque
    500 containing driver text. The full exception goes to the server log; the
    client gets a stable, non-revealing message plus the request id.
    """
    rid = _request_id(request)
    logger.exception("Database error (request_id=%s)", rid)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=_error_body(
            503,
            "The database could not complete this request. Please try again.",
            rid,
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last resort: log the traceback, return a generic message.

    In development the exception text is included to make debugging practical;
    in production it is withheld so internal detail is never sent to a client.
    """
    rid = _request_id(request)
    logger.exception("Unhandled error (request_id=%s)", rid)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(
            500,
            "An unexpected server error occurred.",
            rid,
            details=None if settings.is_production else f"{type(exc).__name__}: {exc}",
        ),
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
