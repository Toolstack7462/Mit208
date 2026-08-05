"""End-to-end smoke test for the PhishGuard API.

Unlike the pytest suite (which drives the app in-process against an in-memory
database), this script exercises a REAL running server over HTTP against the
seeded database. Run it after starting uvicorn:

    python -m app.seed --reset
    uvicorn app.main:app --port 8000
    python smoke_test.py

It is deliberately dependency-free (standard library only) so it can be run on
any machine that can run the backend.
"""
import json
import os
import urllib.error
import urllib.request

# Override with PHISHGUARD_BASE_URL if the server runs on a different port.
BASE = os.environ.get("PHISHGUARD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

TOTAL_CHECKS = 20


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def login(email, pw):
    s, d = call("POST", "/api/auth/login", body={"email": email, "password": pw})
    assert s == 200, (s, d)
    return d["access_token"]


def message_of(payload):
    """Read a message out of the standard error envelope."""
    if isinstance(payload, dict) and "error" in payload:
        return payload["error"].get("message", "")
    return str(payload)


def main():
    ok = 0

    # --- Health -------------------------------------------------------------
    s, health = call("GET", "/health")
    assert s == 200 and health["database_connected"] is True, health
    s, dbinfo = call("GET", "/system/database-status")
    assert s == 200, dbinfo
    print(f"[1] health OK — engine={dbinfo['engine']} connected={health['database_connected']}"); ok += 1

    # --- Authentication -----------------------------------------------------
    analyst = login("analyst@phishguard.local", "Analyst@123")
    staff = login("staff@phishguard.local", "Staff@123")
    print("[2] logins OK (analyst + staff)"); ok += 1

    s, d = call("POST", "/api/auth/login",
                body={"email": "analyst@phishguard.local", "password": "definitely-wrong"})
    assert s == 401, (s, d)
    print(f"[3] wrong password rejected (401): {message_of(d)!r}"); ok += 1

    s, d = call("GET", "/api/emails")
    assert s == 401, (s, d)
    print("[4] unauthenticated request rejected (401)"); ok += 1

    # --- Dashboard ----------------------------------------------------------
    s, stats = call("GET", "/api/dashboard/stats", analyst)
    assert s == 200, stats
    print(f"[5] dashboard: {stats['total_emails']} emails, "
          f"{stats['quarantined']} quarantined, {stats['confirmed_phishing']} confirmed phishing, "
          f"avg risk {stats['avg_risk_score']}, by_level={stats['by_level']}"); ok += 1

    # --- Listing and scoring ------------------------------------------------
    s, emails = call("GET", "/api/emails", analyst)
    assert s == 200 and len(emails) > 0
    top = emails[0]
    print(f"[6] top email #{top['id']} score={top['risk_score']} "
          f"level={top['risk_level']} status={top['status']}"); ok += 1

    s, detail = call("GET", f"/api/emails/{top['id']}", analyst)
    assert s == 200 and detail["reasons"], detail
    print(f"[7] detail #{top['id']} explains its score with {len(detail['reasons'])} indicator(s)"); ok += 1

    # --- Ingestion + scoring of a new message -------------------------------
    s, ingested = call("POST", "/api/emails", analyst, {
        "sender": "security@paypa1-verify.com",
        "sender_name": "PayPal Security",
        "recipient": "staff@phishguard.local",
        "subject": "Urgent: verify your account within 24 hours",
        "body": "Dear customer, we detected unusual activity. Confirm your password "
                "immediately at http://198.51.100.23/login or your account will expire.",
    })
    assert s == 201, ingested
    assert ingested["risk_level"] in ("high", "critical"), ingested
    assert ingested["status"] == "quarantined", ingested
    print(f"[8] ingested phishing email #{ingested['id']} scored {ingested['risk_score']} "
          f"({ingested['risk_level']}) and was auto-quarantined"); ok += 1

    # --- Input validation ---------------------------------------------------
    s, d = call("POST", "/api/emails", analyst,
                {"sender": "", "recipient": "", "subject": "", "body": ""})
    assert s == 422, (s, d)
    print(f"[9] blank sender/recipient rejected (422): {message_of(d)!r}"); ok += 1

    s, d = call("POST", "/api/emails", analyst, {
        "sender": "a@b.com", "recipient": "staff@phishguard.local",
        "subject": "X" * 501, "body": "hi",
    })
    assert s == 422, (s, d)
    print("[10] over-length subject rejected at the API boundary (422, not a DB 500)"); ok += 1

    s, d = call("POST", "/api/emails", analyst, {
        "sender": "not-an-email", "recipient": "staff@phishguard.local",
        "subject": "hi", "body": "hi",
    })
    assert s == 422, (s, d)
    print("[11] malformed sender address rejected (422)"); ok += 1

    # --- Analyst actions ----------------------------------------------------
    inbox = next((e for e in emails if e["status"] == "inbox"), None)
    assert inbox is not None, "expected at least one delivered email in the seed"

    s, d = call("POST", f"/api/emails/{inbox['id']}/quarantine", analyst, {"verdict": "phishing"})
    assert s == 200 and d["status"] == "quarantined", d
    print(f"[12] quarantine email #{inbox['id']} -> {d['status']}"); ok += 1

    s, d = call("POST", f"/api/emails/{inbox['id']}/quarantine", analyst, {"verdict": "phishing"})
    assert s == 409, (s, d)
    print(f"[13] repeating the same action rejected (409): {message_of(d)!r}"); ok += 1

    s, d = call("POST", f"/api/emails/{inbox['id']}/release", analyst, {})
    assert s == 200 and d["status"] == "released", d
    print(f"[14] release email #{inbox['id']} -> {d['status']}"); ok += 1

    s, d = call("POST", f"/api/emails/{ingested['id']}/feedback", analyst,
                {"feedback": "Confirmed credential-harvesting page."})
    assert s == 200, d
    s, d = call("POST", f"/api/emails/{ingested['id']}/feedback", analyst, {"feedback": "   "})
    assert s == 422, (s, d)
    print("[15] feedback accepted with text, rejected when blank (422)"); ok += 1

    # --- Role isolation -----------------------------------------------------
    s, staff_emails = call("GET", "/api/emails", staff)
    assert s == 200 and all(e["recipient"] == "staff@phishguard.local" for e in staff_emails)
    print(f"[16] staff sees only their own {len(staff_emails)} emails"); ok += 1

    s, d = call("POST", f"/api/emails/{staff_emails[0]['id']}/quarantine", staff, {})
    assert s == 403, (s, d)
    s, d = call("GET", "/api/audit-logs", staff)
    assert s == 403, (s, d)
    print("[17] staff blocked from analyst actions and the audit log (403)"); ok += 1

    # --- Release-request workflow ------------------------------------------
    held = next(e for e in staff_emails if e["status"] in ("quarantined", "confirmed_phishing"))

    s, d = call("POST", "/api/release-requests", staff, {"email_id": held["id"], "reason": "too short"})
    assert s == 422, (s, d)
    print("[18] release request without an adequate reason rejected (422)"); ok += 1

    s, req = call("POST", "/api/release-requests", staff,
                  {"email_id": held["id"], "reason": "I was expecting this invoice from our vendor."})
    assert s == 201, req
    s, dup = call("POST", "/api/release-requests", staff,
                  {"email_id": held["id"], "reason": "I was expecting this invoice from our vendor."})
    assert s == 409, (s, dup)
    print(f"[19] release request #{req['id']} created; duplicate rejected (409): {message_of(dup)!r}"); ok += 1

    s, d = call("POST", f"/api/release-requests/{req['id']}/decision", analyst,
                {"status": "approved", "review_note": "Verified with the vendor, releasing."})
    assert s == 200 and d["status"] == "approved", d
    s, released = call("GET", f"/api/emails/{held['id']}", analyst)
    assert released["status"] == "released", released

    s, logs = call("GET", "/api/audit-logs", analyst)
    assert s == 200 and logs
    actions = {}
    for entry in logs:
        actions[entry["action"]] = actions.get(entry["action"], 0) + 1
    assert "release_request_approved" in actions, actions
    print(f"[20] approval released email #{held['id']} and was audited; "
          f"{len(logs)} log entries: {actions}"); ok += 1

    print(f"\nALL {ok}/{TOTAL_CHECKS} CHECKS PASSED")
    return 0 if ok == TOTAL_CHECKS else 1


if __name__ == "__main__":
    raise SystemExit(main())
