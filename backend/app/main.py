"""PhishGuard FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import audit, auth, dashboard, emails, requests


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they do not yet exist (idempotent; safe alongside schema.sql).
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="PhishGuard API",
    description=(
        "PhishGuard — Email phishing detection & quarantine management (MIT208 MVP).\n\n"
        "Rule-based risk scoring with JWT-secured analyst & staff workflows."
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
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(emails.router)
app.include_router(requests.router)
app.include_router(audit.router)
app.include_router(dashboard.router)
