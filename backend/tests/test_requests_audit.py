"""Staff release-request workflow, approval, dashboard and audit-log tests."""


def _staff_held_email(client, staff_headers):
    rows = client.get("/api/emails", headers=staff_headers).json()
    return next(e for e in rows if e["status"] == "quarantined")


def test_staff_creates_release_request(client, staff_headers):
    email = _staff_held_email(client, staff_headers)
    r = client.post("/api/release-requests", headers=staff_headers,
                    json={"email_id": email["id"], "reason": "Expected vendor invoice."})
    assert r.status_code == 201
    assert r.json()["status"] == "pending"


def test_analyst_approves_request_and_releases_email(client, staff_headers, analyst_headers):
    email = _staff_held_email(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": "Please review."}).json()

    dec = client.post(f"/api/release-requests/{req['id']}/decision", headers=analyst_headers,
                      json={"status": "approved", "review_note": "Verified, releasing."})
    assert dec.status_code == 200 and dec.json()["status"] == "approved"

    # underlying email is now released
    detail = client.get(f"/api/emails/{email['id']}", headers=analyst_headers).json()
    assert detail["status"] == "released"


def test_deciding_twice_conflicts(client, staff_headers, analyst_headers):
    email = _staff_held_email(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": "x"}).json()
    client.post(f"/api/release-requests/{req['id']}/decision", headers=analyst_headers,
                json={"status": "denied"})
    again = client.post(f"/api/release-requests/{req['id']}/decision", headers=analyst_headers,
                        json={"status": "approved"})
    assert again.status_code == 409


def test_staff_cannot_decide_requests(client, staff_headers):
    email = _staff_held_email(client, staff_headers)
    req = client.post("/api/release-requests", headers=staff_headers,
                      json={"email_id": email["id"], "reason": "x"}).json()
    r = client.post(f"/api/release-requests/{req['id']}/decision", headers=staff_headers,
                    json={"status": "approved"})
    assert r.status_code == 403


def test_dashboard_stats_shape(client, analyst_headers):
    r = client.get("/api/dashboard/stats", headers=analyst_headers)
    assert r.status_code == 200
    body = r.json()
    for key in ("total_emails", "quarantined", "confirmed_phishing", "by_level", "avg_risk_score"):
        assert key in body


def test_actions_are_audited(client, analyst_headers):
    # perform an action, then confirm it is written to the audit trail
    rows = client.get("/api/emails", headers=analyst_headers).json()
    eid = next(e for e in rows if e["status"] == "inbox")["id"]
    client.post(f"/api/emails/{eid}/quarantine", headers=analyst_headers,
                json={"verdict": "phishing"})

    logs = client.get("/api/audit-logs", headers=analyst_headers).json()
    actions = {log["action"] for log in logs}
    assert "login" in actions          # login is always recorded
    assert "quarantine" in actions     # the action we just performed
    assert all("ip_address" in log for log in logs)


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
