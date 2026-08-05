"""Data-integrity tests: defensive stored-data parsing and database constraints.

Covers the round-two audit findings recorded as BUG-12 to BUG-14 in
docs/BUG_LOG.md. Every case here failed against the previous code.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    EMAIL_STATUSES,
    REQUEST_STATUSES,
    RISK_LEVELS,
    ROLES,
    EmailRecord,
    StaffReleaseRequest,
    User,
)
from app.routers.emails import parse_score_reasons
from tests.conftest import TestingSessionLocal


# --- Defensive parsing of stored score_reasons ------------------------------

def test_parse_score_reasons_handles_valid_json():
    assert parse_score_reasons('["one", "two"]') == ["one", "two"]


def test_parse_score_reasons_handles_empty_and_null():
    assert parse_score_reasons(None) == []
    assert parse_score_reasons("") == []
    assert parse_score_reasons("[]") == []


def test_parse_score_reasons_survives_malformed_json():
    out = parse_score_reasons("{not valid json")
    assert out and "could not be read" in out[0]


def test_parse_score_reasons_survives_valid_json_of_the_wrong_shape():
    assert parse_score_reasons('"just a string"') == ["just a string"]
    assert parse_score_reasons("123") == ["123"]


def test_corrupt_score_reasons_does_not_make_an_email_unreadable(client, analyst_headers):
    """Regression: an unparseable value used to raise inside the handler, so the
    whole email returned HTTP 500 even though score, level and body were intact."""
    db = TestingSessionLocal()
    email = db.query(EmailRecord).first()
    email_id, score, level = email.id, email.risk_score, email.risk_level
    email.score_reasons = "{not valid json"
    db.commit()
    db.close()

    r = client.get(f"/api/emails/{email_id}", headers=analyst_headers)
    assert r.status_code == 200, "a corrupt explanation must not hide the record"
    body = r.json()
    assert body["risk_score"] == score
    assert body["risk_level"] == level
    assert body["body"]
    assert "could not be read" in " ".join(body["reasons"])


def test_email_list_still_works_when_one_row_is_corrupt(client, analyst_headers):
    db = TestingSessionLocal()
    db.query(EmailRecord).first().score_reasons = "!!! broken"
    db.commit()
    db.close()

    r = client.get("/api/emails", headers=analyst_headers)
    assert r.status_code == 200 and r.json()


# --- Database CHECK constraints ---------------------------------------------
# The API validates these values, but a direct SQL write (a migration, a psql
# session, a future script) previously bypassed every one of them.

def test_database_rejects_an_unknown_role():
    db = TestingSessionLocal()
    try:
        db.add(User(email="rogue@phishguard.local", full_name="Rogue",
                    hashed_password="x", role="superadmin"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_database_accepts_every_documented_role():
    db = TestingSessionLocal()
    try:
        for i, role in enumerate(ROLES):
            db.add(User(email=f"role{i}@phishguard.local", full_name=f"R{i}",
                        hashed_password="x", role=role))
        db.commit()
    finally:
        db.close()


def _new_email(**overrides):
    base = dict(
        message_id="<constraint-test@phishguard.local>",
        sender="a@b.com", recipient="staff@phishguard.local",
        subject="s", body="b", status="inbox",
        risk_score=10, risk_level="low", score_reasons="[]",
    )
    base.update(overrides)
    return EmailRecord(**base)


@pytest.mark.parametrize("field,bad_value", [
    ("status", "deleted"),
    ("risk_level", "extreme"),
    ("auth_spf", "maybe"),
    ("auth_dkim", "maybe"),
    ("auth_dmarc", "maybe"),
])
def test_database_rejects_unknown_enumerated_email_values(field, bad_value):
    db = TestingSessionLocal()
    try:
        db.add(_new_email(**{field: bad_value}))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


@pytest.mark.parametrize("score", [-1, 101, 1000])
def test_database_rejects_a_risk_score_outside_zero_to_one_hundred(score):
    db = TestingSessionLocal()
    try:
        db.add(_new_email(risk_score=score))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_database_accepts_the_score_boundaries():
    db = TestingSessionLocal()
    try:
        db.add(_new_email(message_id="<zero@phishguard.local>", risk_score=0))
        db.add(_new_email(message_id="<hundred@phishguard.local>", risk_score=100,
                          risk_level="critical"))
        db.commit()
    finally:
        db.close()


def test_database_accepts_every_documented_email_status():
    db = TestingSessionLocal()
    try:
        for i, st in enumerate(EMAIL_STATUSES):
            db.add(_new_email(message_id=f"<st{i}@phishguard.local>", status=st))
        for i, lvl in enumerate(RISK_LEVELS):
            db.add(_new_email(message_id=f"<lvl{i}@phishguard.local>", risk_level=lvl))
        db.commit()
    finally:
        db.close()


# --- Partial unique index on pending release requests -----------------------

def _seed_request(db, *, status="pending", email_id=1, user_id=3, reviewed=False):
    from datetime import datetime, timezone
    return StaffReleaseRequest(
        email_id=email_id, requested_by=user_id,
        reason="I was expecting this invoice from our vendor.",
        status=status,
        reviewed_by=user_id if reviewed else None,
        reviewed_at=datetime.now(timezone.utc) if reviewed else None,
    )


def test_database_blocks_a_second_pending_request_for_the_same_email_and_user():
    """The API check and the INSERT are separate statements, so two concurrent
    submissions could both pass. The partial unique index makes it atomic."""
    db = TestingSessionLocal()
    try:
        db.add(_seed_request(db))
        db.commit()
        db.add(_seed_request(db))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_the_index_only_constrains_pending_rows():
    """Two DECIDED requests for the same email and user are legitimate history."""
    db = TestingSessionLocal()
    try:
        db.add(_seed_request(db, status="denied", reviewed=True))
        db.add(_seed_request(db, status="denied", reviewed=True))
        db.commit()
    finally:
        db.close()


def test_a_new_pending_request_is_allowed_once_the_previous_one_is_decided():
    db = TestingSessionLocal()
    try:
        db.add(_seed_request(db, status="approved", reviewed=True))
        db.commit()
        db.add(_seed_request(db, status="pending"))
        db.commit()
    finally:
        db.close()


def test_different_users_may_each_have_a_pending_request_for_one_email():
    db = TestingSessionLocal()
    try:
        db.add(_seed_request(db, user_id=1))
        db.add(_seed_request(db, user_id=2))
        db.commit()
    finally:
        db.close()


# --- Decision-completeness constraint ---------------------------------------

@pytest.mark.parametrize("status", [s for s in REQUEST_STATUSES if s != "pending"])
def test_a_decided_request_must_record_its_reviewer(status):
    db = TestingSessionLocal()
    try:
        db.add(_seed_request(db, status=status, reviewed=False))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_a_pending_request_must_not_record_a_reviewer():
    db = TestingSessionLocal()
    try:
        db.add(_seed_request(db, status="pending", reviewed=True))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


# --- Transaction atomicity --------------------------------------------------

def test_a_failure_mid_action_leaves_no_partial_write(client, analyst_headers, monkeypatch):
    """An analyst action writes three rows (status change, review, audit entry).
    If the last one fails, the first two must not survive."""
    from fastapi.testclient import TestClient
    import app.routers.emails as emails_router
    from app.main import app

    rows = client.get("/api/emails", headers=analyst_headers).json()
    target = next(e for e in rows if e["status"] == "inbox")
    before = target["status"]

    def _explode(*args, **kwargs):
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(emails_router, "record_audit", _explode)

    # raise_server_exceptions=False makes the test client behave like a real
    # deployment, where the global handler turns the fault into a 500 response.
    with TestClient(app, raise_server_exceptions=False) as failing_client:
        r = failing_client.post(f"/api/emails/{target['id']}/quarantine",
                                headers=analyst_headers, json={"verdict": "phishing"})
    assert r.status_code == 500

    monkeypatch.undo()

    # The status change and the review row must both have been rolled back.
    after = client.get(f"/api/emails/{target['id']}", headers=analyst_headers).json()
    assert after["status"] == before, "the status change survived a failed transaction"

    db = TestingSessionLocal()
    try:
        from app.models import AnalystReview
        orphans = db.query(AnalystReview).filter(
            AnalystReview.email_id == target["id"]).count()
        assert orphans == 0, "an orphan review row survived a failed transaction"
    finally:
        db.close()


def test_the_api_decision_path_satisfies_the_constraint(client, staff_headers, analyst_headers):
    """End-to-end proof that the real workflow writes rows the database accepts."""
    rows = client.get("/api/emails", headers=staff_headers).json()
    eid = next(e for e in rows if e["status"] == "quarantined")["id"]
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": eid,
                            "reason": "I was expecting this invoice from our vendor."})
    assert req.status_code == 201
    dec = client.post(f"/api/release-requests/{req.json()['id']}/decision",
                      headers=analyst_headers,
                      json={"status": "approved", "review_note": "Verified."})
    assert dec.status_code == 200
    assert dec.json()["reviewed_by"] is not None


# --- Concurrency: the race the partial unique index exists to stop -----------

def test_a_concurrent_duplicate_request_gets_409_not_503(client, staff_headers, monkeypatch):
    """The duplicate pre-check and the INSERT are two statements, so a concurrent
    request can commit its own pending row in between.

    The index correctly rejects the loser, but that arrived as a generic 503
    "the database could not complete this request, please try again" — the wrong
    status, and misleading advice, because retrying can never succeed. It must be
    the same 409 a sequential duplicate receives.

    Found by running this suite against real PostgreSQL; see docs/BUG_LOG.md
    BUG-16.
    """
    import app.routers.requests as req_router

    rows = client.get("/api/emails", headers=staff_headers).json()
    eid = next(e for e in rows if e["status"] == "quarantined")["id"]
    reason = "I was expecting this invoice from our supplier."

    first = client.post("/api/release-requests", headers=staff_headers,
                        json={"email_id": eid, "reason": reason})
    assert first.status_code == 201

    # Reproduce the race window: the pre-check reports "no open request" even
    # though one has just been committed by another worker.
    monkeypatch.setattr(req_router, "find_open_request", lambda *a, **k: None)

    second = client.post("/api/release-requests", headers=staff_headers,
                         json={"email_id": eid, "reason": reason})
    assert second.status_code == 409, (
        f"expected 409 from the index violation, got {second.status_code}"
    )
    assert "already have a pending" in second.json()["error"]["message"]


def test_the_losing_concurrent_request_writes_nothing(client, staff_headers, monkeypatch):
    """The rejected attempt must not leave a row or an audit entry behind."""
    import app.routers.requests as req_router

    rows = client.get("/api/emails", headers=staff_headers).json()
    eid = next(e for e in rows if e["status"] == "quarantined")["id"]
    reason = "I was expecting this invoice from our supplier."

    client.post("/api/release-requests", headers=staff_headers,
                json={"email_id": eid, "reason": reason})
    monkeypatch.setattr(req_router, "find_open_request", lambda *a, **k: None)
    client.post("/api/release-requests", headers=staff_headers,
                json={"email_id": eid, "reason": reason})
    monkeypatch.undo()

    mine = [r for r in client.get("/api/release-requests", headers=staff_headers).json()
            if r["email_id"] == eid and r["status"] == "pending"]
    assert len(mine) == 1, "the losing request left a row behind"


def test_an_unrelated_integrity_error_is_not_masked_as_a_duplicate(client, staff_headers,
                                                                   monkeypatch):
    """Only the pending-request index maps to 409. Any other integrity failure
    must keep its own handling rather than being mislabelled."""
    import app.routers.requests as req_router
    from sqlalchemy.exc import IntegrityError

    rows = client.get("/api/emails", headers=staff_headers).json()
    eid = next(e for e in rows if e["status"] == "quarantined")["id"]

    def _boom(*args, **kwargs):
        raise IntegrityError("INSERT ...", {}, Exception("some other constraint"))

    monkeypatch.setattr(req_router, "record_audit", _boom)

    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as failing:
        r = failing.post("/api/release-requests", headers=staff_headers,
                         json={"email_id": eid,
                               "reason": "I was expecting this vendor invoice."})
    assert r.status_code != 409, "an unrelated integrity error must not read as a duplicate"
    assert r.status_code >= 500


@pytest.mark.parametrize("driver_message,expected", [
    # PostgreSQL names the index...
    ('duplicate key value violates unique constraint '
     '"uq_request_one_pending_per_email_user"', True),
    # ...while SQLite names the columns instead. Matching only one of these left
    # the fix working on PostgreSQL and broken on SQLite.
    ("UNIQUE constraint failed: staff_release_requests.email_id, "
     "staff_release_requests.requested_by", True),
    # Anything else must not be mistaken for a duplicate request.
    ('duplicate key value violates unique constraint "users_email_key"', False),
    ("null value in column \"reason\" violates not-null constraint", False),
    ('new row violates check constraint "ck_request_status"', False),
])
def test_pending_request_conflict_is_recognised_on_both_engines(driver_message, expected):
    """Both drivers' wording must be recognised, and nothing else."""
    from sqlalchemy.exc import IntegrityError as IE
    from app.routers.requests import is_pending_request_conflict
    exc = IE("INSERT ...", {}, Exception(driver_message))
    assert is_pending_request_conflict(exc) is expected
