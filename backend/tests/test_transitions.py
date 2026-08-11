"""Regression tests for the email state machine and the staff-only request rule.

Round-three audit findings, recorded as BUG-17 and BUG-18 in docs/BUG_LOG.md.
Every case in this file was accepted by the previous code:

* BUG-17  The API had no source-state rules. ``_apply_action`` refused only an
          action whose target equalled the current status, so "release" worked
          on email that had never been held and "quarantine" silently downgraded
          a confirmed phishing verdict — each one writing a review row and an
          audit entry describing a decision that had not been made.
* BUG-18  ``POST /api/release-requests`` accepted analyst and admin callers, and
          guarded ownership with ``if current.role == "staff"``, so those roles
          could raise a request against any user's mailbox.
"""
import re
from pathlib import Path

import pytest

from app.models import EMAIL_STATUSES, AnalystReview, EmailRecord, User
from app.transitions import (
    ACTION_TARGET_STATUS,
    ALLOWED_SOURCE_STATUSES,
    HOLDABLE_STATUSES,
    allowed_actions,
    is_allowed,
)
from app.security import hash_password
from tests.conftest import TestingSessionLocal

REASON = "I was expecting this invoice from our vendor."


# --- The rules themselves ----------------------------------------------------

@pytest.mark.parametrize("action,status,expected", [
    # release applies only to email that is actually being withheld.
    ("release", "quarantined", True),
    ("release", "confirmed_phishing", True),
    ("release", "inbox", False),
    ("release", "safe", False),
    ("release", "released", False),
    # quarantine applies to email currently being delivered. Not to a confirmed
    # phishing verdict: that would downgrade it.
    ("quarantine", "inbox", True),
    ("quarantine", "released", True),
    ("quarantine", "safe", True),
    ("quarantine", "quarantined", False),
    ("quarantine", "confirmed_phishing", False),
    # a phishing verdict must stay reachable from every other state.
    ("confirm_phishing", "inbox", True),
    ("confirm_phishing", "quarantined", True),
    ("confirm_phishing", "released", True),
    ("confirm_phishing", "safe", True),
    ("confirm_phishing", "confirmed_phishing", False),
])
def test_the_transition_table_matches_the_documented_rules(action, status, expected):
    assert is_allowed(action, status) is expected


@pytest.mark.parametrize("status", EMAIL_STATUSES)
def test_feedback_is_valid_from_every_status(status):
    """Feedback records an analyst note and changes nothing, so no state blocks it."""
    assert is_allowed("feedback", status) is True
    assert "feedback" in allowed_actions(status)


@pytest.mark.parametrize("status", EMAIL_STATUSES)
def test_no_action_can_target_the_status_it_starts_from(status):
    """A transition that would leave the status unchanged is never offered."""
    for action in allowed_actions(status):
        assert ACTION_TARGET_STATUS[action] != status


def test_holdable_statuses_are_exactly_the_release_sources():
    """The release-request rule and the release action must not drift apart."""
    assert HOLDABLE_STATUSES == ALLOWED_SOURCE_STATUSES["release"]


def test_every_status_keeps_at_least_one_way_out():
    """No status may be a dead end, or an email could never be acted on again."""
    for status in EMAIL_STATUSES:
        moves = [a for a in allowed_actions(status) if ACTION_TARGET_STATUS[a]]
        assert moves, f"{status} has no outgoing transition"


# --- The frontend mirror -----------------------------------------------------

def _parse_js_string_lists(source: str, const_name: str) -> dict[str, list[str]]:
    """Pull ``{ key: ["a", "b"] }`` out of an exported const in the JS mirror."""
    block = re.search(rf"export const {const_name} = \{{(.*?)\n\}};", source, re.S)
    assert block, f"{const_name} not found in the frontend mirror"
    return {
        key: re.findall(r'"([^"]+)"', values)
        for key, values in re.findall(r"(\w+):\s*\[([^\]]*)\]", block.group(1))
    }


def test_the_frontend_mirror_matches_the_backend_rules():
    """frontend/src/lib/transitions.js decides which buttons are enabled. If it
    drifts from this table the interface offers actions the server refuses (or
    hides ones it would accept), which is what BUG-17 looked like to a user."""
    js = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "transitions.js"
    assert js.exists(), f"frontend mirror missing at {js}"
    mirrored = _parse_js_string_lists(js.read_text(encoding="utf-8"), "ALLOWED_SOURCE_STATUSES")

    assert mirrored == {a: list(s) for a, s in ALLOWED_SOURCE_STATUSES.items()}, (
        "frontend/src/lib/transitions.js disagrees with app/transitions.py"
    )


# --- Invalid transitions are refused over the API ----------------------------

def _emails(client, headers):
    return client.get("/api/emails", headers=headers).json()


def _by_status(client, headers, status):
    return next(e for e in _emails(client, headers) if e["status"] == status)


def test_releasing_an_email_that_was_never_held_is_refused(client, analyst_headers):
    """The headline BUG-17 case: 'release' on a delivered email used to return
    200, flip it to 'released' and record an analyst review for it."""
    email = _by_status(client, analyst_headers, "inbox")

    r = client.post(f"/api/emails/{email['id']}/release", headers=analyst_headers, json={})

    assert r.status_code == 409
    message = r.json()["error"]["message"]
    assert "quarantined" in message and "confirmed_phishing" in message, message

    after = client.get(f"/api/emails/{email['id']}", headers=analyst_headers).json()
    assert after["status"] == "inbox", "the refused action changed the email anyway"


def test_a_refused_transition_writes_no_review_and_no_audit_entry(client, analyst_headers):
    email = _by_status(client, analyst_headers, "inbox")
    before = len(client.get("/api/audit-logs", headers=analyst_headers).json())

    client.post(f"/api/emails/{email['id']}/release", headers=analyst_headers, json={})

    after = len(client.get("/api/audit-logs", headers=analyst_headers).json())
    assert after == before, "a refused action still appended an audit entry"

    db = TestingSessionLocal()
    try:
        assert db.query(AnalystReview).filter(AnalystReview.email_id == email["id"]).count() == 0
    finally:
        db.close()


def test_quarantine_cannot_downgrade_a_confirmed_phishing_verdict(client, analyst_headers):
    email = _by_status(client, analyst_headers, "quarantined")
    confirmed = client.post(f"/api/emails/{email['id']}/confirm-phishing",
                            headers=analyst_headers, json={"verdict": "phishing"})
    assert confirmed.status_code == 200

    r = client.post(f"/api/emails/{email['id']}/quarantine",
                    headers=analyst_headers, json={"verdict": "phishing"})
    assert r.status_code == 409

    after = client.get(f"/api/emails/{email['id']}", headers=analyst_headers).json()
    assert after["status"] == "confirmed_phishing"


def test_repeating_an_action_still_reports_the_no_op_message(client, analyst_headers):
    """The friendlier 'already X' wording must survive the new rule, because it
    is the case a user is most likely to hit by double-clicking."""
    email = _by_status(client, analyst_headers, "inbox")
    client.post(f"/api/emails/{email['id']}/quarantine", headers=analyst_headers, json={})

    r = client.post(f"/api/emails/{email['id']}/quarantine", headers=analyst_headers, json={})
    assert r.status_code == 409
    assert "already" in r.json()["error"]["message"].lower()


@pytest.mark.parametrize("status", EMAIL_STATUSES)
def test_feedback_is_accepted_whatever_the_email_status(client, analyst_headers, status):
    db = TestingSessionLocal()
    try:
        email = db.query(EmailRecord).first()
        email.status = status
        email_id = email.id
        db.commit()
    finally:
        db.close()

    r = client.post(f"/api/emails/{email_id}/feedback", headers=analyst_headers,
                    json={"feedback": "Reviewed as part of the weekly sample."})
    assert r.status_code == 200


# --- Valid transitions still work -------------------------------------------

@pytest.mark.parametrize("start,endpoint,expected", [
    ("inbox", "quarantine", "quarantined"),
    ("quarantined", "release", "released"),
    ("released", "quarantine", "quarantined"),
    ("released", "confirm-phishing", "confirmed_phishing"),
    ("confirmed_phishing", "release", "released"),
    ("safe", "quarantine", "quarantined"),
])
def test_every_permitted_transition_is_accepted(client, analyst_headers, start, endpoint, expected):
    db = TestingSessionLocal()
    try:
        email = db.query(EmailRecord).first()
        email.status = start
        email_id = email.id
        db.commit()
    finally:
        db.close()

    r = client.post(f"/api/emails/{email_id}/{endpoint}", headers=analyst_headers, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == expected


# --- Release requests are staff-only, and only for the caller's own email -----

def _held_email_for(client, headers):
    return _by_status(client, headers, "quarantined")


def test_staff_may_request_release_of_their_own_held_email(client, staff_headers):
    eid = _held_email_for(client, staff_headers)["id"]
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": eid, "reason": REASON})
    assert r.status_code == 201


@pytest.mark.parametrize("role", ["analyst", "admin"])
def test_an_analyst_or_admin_cannot_raise_a_release_request(client, staff_headers,
                                                            analyst_headers, admin_headers, role):
    """BUG-18. An analyst can already release an email directly; letting them
    file a request as well produced a queue entry that claimed the recipient had
    asked for something they never asked for."""
    headers = analyst_headers if role == "analyst" else admin_headers
    eid = _held_email_for(client, staff_headers)["id"]

    r = client.post("/api/release-requests", headers=headers,
                    json={"email_id": eid, "reason": REASON})

    assert r.status_code == 403
    assert "staff" in r.json()["error"]["message"].lower()


def test_reviewers_keep_read_access_to_the_whole_queue(client, staff_headers, analyst_headers):
    """Blocking creation must not block review — the analyst still needs the list."""
    eid = _held_email_for(client, staff_headers)["id"]
    client.post("/api/release-requests", headers=staff_headers,
                json={"email_id": eid, "reason": REASON})

    rows = client.get("/api/release-requests", headers=analyst_headers).json()
    assert any(r["email_id"] == eid for r in rows)


def _other_staff_held_email(db) -> int:
    """A quarantined email addressed to a different staff member."""
    db.add(User(email="dana@phishguard.local", full_name="Dana Other", role="staff",
                hashed_password=hash_password("Other@1234")))
    email = EmailRecord(
        message_id="<other-mailbox@phishguard.local>",
        sender="security@paypa1-support.com", recipient="dana@phishguard.local",
        subject="Urgent: verify your account", body="Confirm your password immediately.",
        status="quarantined", risk_score=88, risk_level="critical", score_reasons="[]",
    )
    db.add(email)
    db.commit()
    return email.id


def test_staff_cannot_request_release_of_someone_else_s_email(client, staff_headers):
    db = TestingSessionLocal()
    try:
        other_id = _other_staff_held_email(db)
    finally:
        db.close()

    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": other_id, "reason": REASON})
    assert r.status_code == 403
    assert "your own" in r.json()["error"]["message"].lower()


def test_the_ownership_rule_is_not_conditional_on_role(client, analyst_headers, staff_headers):
    """The old guard read ``if current.role == "staff"``, so any other role
    skipped the ownership check entirely. Neither branch may exist now: the
    endpoint is staff-only AND ownership is always enforced."""
    db = TestingSessionLocal()
    try:
        other_id = _other_staff_held_email(db)
    finally:
        db.close()

    assert client.post("/api/release-requests", headers=analyst_headers,
                       json={"email_id": other_id, "reason": REASON}).status_code == 403
    assert client.post("/api/release-requests", headers=staff_headers,
                       json={"email_id": other_id, "reason": REASON}).status_code == 403


# --- Approving a request obeys the same state machine ------------------------

def test_approving_a_stale_request_cannot_force_a_released_email(client, staff_headers,
                                                                 analyst_headers):
    """A request can sit in the queue while the email is acted on elsewhere.
    Approval used to set status='released' unconditionally, so a request could
    'release' an email that was no longer in a releasable state."""
    email = _held_email_for(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": REASON}).json()

    # Meanwhile the analyst releases it directly, then re-quarantines it is not
    # needed — a plain release is enough to invalidate the pending request.
    assert client.post(f"/api/emails/{email['id']}/release",
                       headers=analyst_headers, json={}).status_code == 200

    decision = client.post(f"/api/release-requests/{req['id']}/decision",
                           headers=analyst_headers,
                           json={"status": "approved", "review_note": "Vendor verified."})

    assert decision.status_code == 409
    assert "release" in decision.json()["error"]["message"].lower()

    still_pending = [r for r in client.get("/api/release-requests", headers=analyst_headers).json()
                     if r["id"] == req["id"]]
    assert still_pending[0]["status"] == "pending", "the refused decision was applied anyway"


def test_a_stale_request_can_still_be_denied(client, staff_headers, analyst_headers):
    """Denial changes no email status, so it must stay available — otherwise a
    request against an already-released email could never be cleared."""
    email = _held_email_for(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": REASON}).json()
    client.post(f"/api/emails/{email['id']}/release", headers=analyst_headers, json={})

    decision = client.post(f"/api/release-requests/{req['id']}/decision",
                           headers=analyst_headers,
                           json={"status": "denied", "review_note": "Already released directly."})
    assert decision.status_code == 200
    assert decision.json()["status"] == "denied"


def test_approval_still_works_on_a_confirmed_phishing_email(client, staff_headers,
                                                            analyst_headers):
    """confirmed_phishing is a holdable status, so the queue path must accept it
    exactly as a direct release does."""
    email = _held_email_for(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": REASON}).json()
    client.post(f"/api/emails/{email['id']}/confirm-phishing",
                headers=analyst_headers, json={"verdict": "phishing"})

    decision = client.post(f"/api/release-requests/{req['id']}/decision",
                           headers=analyst_headers,
                           json={"status": "approved", "review_note": "False positive confirmed."})
    assert decision.status_code == 200
    detail = client.get(f"/api/emails/{email['id']}", headers=analyst_headers).json()
    assert detail["status"] == "released"
