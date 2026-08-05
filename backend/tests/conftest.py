"""Pytest fixtures for the PhishGuard API test suite.

By default each test runs against an isolated in-memory SQLite database (never
the real ``phishguard.db``), seeded with the same synthetic users and emails used
by the demo. The FastAPI ``get_db`` dependency is overridden so the app talks to
the test database.

Running the same suite against PostgreSQL
-----------------------------------------
PostgreSQL is the assessed target, and the two engines do not behave identically
— SQLite ignores declared string lengths, for example. Set ``TEST_DATABASE_URL``
to run every test against a real PostgreSQL database instead:

    # PowerShell
    $env:TEST_DATABASE_URL = "postgresql+psycopg2://user:pass@localhost:5432/phishguard_test"
    python -m pytest

Use a database that exists only for testing: the fixture drops and recreates all
tables around every test.
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, session_scope
from app.main import app
from app.models import AuditLog, EmailRecord, StaffReleaseRequest, User
from app.routers.auth import login_limiter
from app.scoring import score_email
from app.security import hash_password

# --- Test database ----------------------------------------------------------
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()

if TEST_DATABASE_URL:
    # A real server (normally PostgreSQL). No StaticPool: each connection is real,
    # and pool_pre_ping avoids a stale connection between tests.
    test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
else:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # single shared in-memory connection across threads
    )

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def pytest_report_header() -> str:
    """Name the engine under test, so a run's output says what it proved."""
    return f"phishguard test database: {test_engine.dialect.name}"

USERS = [
    ("admin@phishguard.local", "Alex Admin", "admin", "Admin@123"),
    ("analyst@phishguard.local", "Sam Analyst", "analyst", "Analyst@123"),
    ("staff@phishguard.local", "Riley Staff", "staff", "Staff@123"),
]

# (sender, sender_name, recipient, subject, body)
EMAILS = [
    (
        "security@paypa1-support.com", "PayPal Security", "staff@phishguard.local",
        "Urgent: Your account has been suspended - verify now",
        "Dear customer, we detected unusual activity. Your account suspended until you "
        "verify your identity. Confirm your password immediately or it will expire within "
        "24 hours. <a href=\"http://198.51.100.23/login\">https://www.paypal.com/login</a>",
    ),
    (
        "newsletter@techweekly.com", "Tech Weekly", "staff@phishguard.local",
        "Your Monday tech digest is here",
        "Hi Riley, here are this week's top engineering reads. Read online at "
        "https://techweekly.com/digest . Happy reading!",
    ),
]


def _seed(db):
    users = {}
    for email, name, role, pw in USERS:
        u = User(email=email, full_name=name, role=role, hashed_password=hash_password(pw))
        db.add(u)
        users[email] = u
    db.flush()

    for i, (sender, sname, recipient, subject, body) in enumerate(EMAILS):
        r = score_email(sender, subject, body, sname)
        db.add(EmailRecord(
            message_id=f"<test-{i + 1}@phishguard.local>",
            sender=sender, sender_name=sname, recipient=recipient,
            subject=subject, body=body,
            status="quarantined" if r.level in ("high", "critical") else "inbox",
            risk_score=r.score, risk_level=r.level, score_reasons=json.dumps(r.reasons),
            auth_spf=r.spf, auth_dkim=r.dkim, auth_dmarc=r.dmarc, ai_generated=r.ai_generated,
        ))
    db.commit()


@pytest.fixture(autouse=True)
def _setup_database():
    """Give every test a freshly created + seeded database so tests stay isolated
    regardless of the order in which they mutate email state."""
    # Drop first as well as last: on a real server a previous interrupted run can
    # leave tables behind, and create_all would then silently reuse dirty data.
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        _seed(db)
    finally:
        db.close()

    def _override_get_db():
        # Reuse the application's own session_scope so the rollback-on-failure
        # behaviour under test is the real implementation, not a copy of it.
        yield from session_scope(TestingSessionLocal)

    app.dependency_overrides[get_db] = _override_get_db
    # The login rate limiter keeps process-wide state; clear it so a test that
    # deliberately fails logins cannot lock out the tests that run after it.
    login_limiter.clear()
    yield
    login_limiter.clear()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client():
    return TestClient(app)


def _token(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def analyst_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'analyst@phishguard.local', 'Analyst@123')}"}


@pytest.fixture()
def staff_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'staff@phishguard.local', 'Staff@123')}"}


@pytest.fixture()
def admin_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'admin@phishguard.local', 'Admin@123')}"}
