"""Release-request workflow guard tests.

The pre-audit API returned 201 for every case below: duplicate requests, an
empty justification, and requests against email that was never held. See
docs/BUG_LOG.md entry BUG-02.
"""


def _held_email(client, staff_headers):
    rows = client.get("/api/emails", headers=staff_headers).json()
    return next(e for e in rows if e["status"] == "quarantined")


def _inbox_email(client, staff_headers):
    rows = client.get("/api/emails", headers=staff_headers).json()
    return next(e for e in rows if e["status"] == "inbox")


REASON = "I was expecting this invoice from our vendor."


# --- Duplicate suppression --------------------------------------------------

def test_duplicate_pending_request_is_rejected(client, staff_headers):
    eid = _held_email(client, staff_headers)["id"]
    first = client.post("/api/release-requests", headers=staff_headers,
                        json={"email_id": eid, "reason": REASON})
    second = client.post("/api/release-requests", headers=staff_headers,
                         json={"email_id": eid, "reason": REASON})
    assert first.status_code == 201
    assert second.status_code == 409
    assert "already have a pending" in second.json()["error"]["message"]


def test_a_new_request_is_allowed_after_the_previous_one_was_denied(client,
                                                                   staff_headers,
                                                                   analyst_headers):
    """Denial must not permanently bar the user — only an OPEN request blocks."""
    eid = _held_email(client, staff_headers)["id"]
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": eid, "reason": REASON}).json()
    client.post(f"/api/release-requests/{req['id']}/decision", headers=analyst_headers,
                json={"status": "denied", "review_note": "Confirmed malicious."})
    again = client.post("/api/release-requests", headers=staff_headers,
                        json={"email_id": eid, "reason": "Vendor has now confirmed it is genuine."})
    assert again.status_code == 201


def test_only_one_pending_request_row_exists_after_duplicates(client, staff_headers):
    eid = _held_email(client, staff_headers)["id"]
    for _ in range(3):
        client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": eid, "reason": REASON})
    rows = client.get("/api/release-requests", headers=staff_headers).json()
    pending = [r for r in rows if r["email_id"] == eid and r["status"] == "pending"]
    assert len(pending) == 1


# --- Justification required -------------------------------------------------

def test_missing_reason_is_rejected(client, staff_headers):
    eid = _held_email(client, staff_headers)["id"]
    r = client.post("/api/release-requests", headers=staff_headers, json={"email_id": eid})
    assert r.status_code == 422


def test_empty_reason_is_rejected(client, staff_headers):
    eid = _held_email(client, staff_headers)["id"]
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": eid, "reason": ""})
    assert r.status_code == 422


def test_whitespace_only_reason_is_rejected(client, staff_headers):
    eid = _held_email(client, staff_headers)["id"]
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": eid, "reason": "              "})
    assert r.status_code == 422


def test_oversized_reason_is_rejected(client, staff_headers):
    eid = _held_email(client, staff_headers)["id"]
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": eid, "reason": "x" * 2001})
    assert r.status_code == 422


# --- Only held email can be requested ---------------------------------------

def test_request_against_a_delivered_email_is_rejected(client, staff_headers):
    eid = _inbox_email(client, staff_headers)["id"]
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": eid, "reason": REASON})
    assert r.status_code == 409
    assert "not being held" in r.json()["error"]["message"]


def test_request_against_an_already_released_email_is_rejected(client, staff_headers,
                                                               analyst_headers):
    email = _held_email(client, staff_headers)
    client.post(f"/api/emails/{email['id']}/release", headers=analyst_headers, json={})
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": email["id"], "reason": REASON})
    assert r.status_code == 409


def test_request_for_a_missing_email_is_404(client, staff_headers):
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": 999999, "reason": REASON})
    assert r.status_code == 404


# --- Decision path ----------------------------------------------------------

def test_invalid_decision_status_is_rejected(client, staff_headers, analyst_headers):
    eid = _held_email(client, staff_headers)["id"]
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": eid, "reason": REASON}).json()
    r = client.post(f"/api/release-requests/{req['id']}/decision",
                    headers=analyst_headers, json={"status": "maybe"})
    assert r.status_code == 422


def test_approval_records_an_analyst_review_and_audit_entry(client, staff_headers,
                                                            analyst_headers):
    """Approving through the request queue must leave the same trail as a direct
    analyst release, so analyst_reviews stays complete."""
    email = _held_email(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": REASON}).json()
    dec = client.post(f"/api/release-requests/{req['id']}/decision", headers=analyst_headers,
                      json={"status": "approved", "review_note": "Vendor verified."})
    assert dec.status_code == 200

    detail = client.get(f"/api/emails/{email['id']}", headers=analyst_headers).json()
    assert detail["status"] == "released"

    logs = client.get("/api/audit-logs", headers=analyst_headers).json()
    assert any(log["action"] == "release_request_approved" for log in logs)


def test_denial_leaves_the_email_held(client, staff_headers, analyst_headers):
    email = _held_email(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": REASON}).json()
    client.post(f"/api/release-requests/{req['id']}/decision", headers=analyst_headers,
                json={"status": "denied", "review_note": "Confirmed phishing."})
    detail = client.get(f"/api/emails/{email['id']}", headers=analyst_headers).json()
    assert detail["status"] == "quarantined"


def test_staff_sees_only_their_own_requests(client, staff_headers, analyst_headers):
    eid = _held_email(client, staff_headers)["id"]
    client.post("/api/release-requests", headers=staff_headers,
                json={"email_id": eid, "reason": REASON})
    rows = client.get("/api/release-requests", headers=staff_headers).json()
    assert rows
    assert all(r["requested_by"] == rows[0]["requested_by"] for r in rows)
