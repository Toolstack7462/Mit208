"""Email listing, detail, analyst actions and staff isolation tests."""


def test_analyst_lists_all_emails(client, analyst_headers):
    r = client.get("/api/emails", headers=analyst_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2  # seeded emails


def test_emails_sorted_by_risk_desc(client, analyst_headers):
    rows = client.get("/api/emails", headers=analyst_headers).json()
    scores = [e["risk_score"] for e in rows]
    assert scores == sorted(scores, reverse=True)


def test_staff_only_sees_own_mail(client, staff_headers):
    rows = client.get("/api/emails", headers=staff_headers).json()
    assert rows  # staff@ has seeded mail
    assert all(e["recipient"] == "staff@phishguard.local" for e in rows)


def test_email_detail_includes_reasons(client, analyst_headers):
    rows = client.get("/api/emails", headers=analyst_headers).json()
    eid = rows[0]["id"]
    detail = client.get(f"/api/emails/{eid}", headers=analyst_headers).json()
    assert "reasons" in detail and isinstance(detail["reasons"], list)
    assert "auth_spf" in detail


def test_quarantine_then_release_transitions(client, analyst_headers):
    rows = client.get("/api/emails", headers=analyst_headers).json()
    # pick a low-risk inbox email so we control the transition
    target = next(e for e in rows if e["status"] == "inbox")
    eid = target["id"]

    q = client.post(f"/api/emails/{eid}/quarantine", headers=analyst_headers,
                    json={"verdict": "phishing"})
    assert q.status_code == 200 and q.json()["status"] == "quarantined"

    rel = client.post(f"/api/emails/{eid}/release", headers=analyst_headers, json={})
    assert rel.status_code == 200 and rel.json()["status"] == "released"


def test_confirm_phishing_sets_status(client, analyst_headers):
    rows = client.get("/api/emails", headers=analyst_headers).json()
    eid = next(e for e in rows if e["risk_level"] in ("high", "critical"))["id"]
    r = client.post(f"/api/emails/{eid}/confirm-phishing", headers=analyst_headers,
                    json={"verdict": "phishing"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed_phishing"


def test_feedback_requires_text(client, analyst_headers):
    rows = client.get("/api/emails", headers=analyst_headers).json()
    eid = rows[0]["id"]
    r = client.post(f"/api/emails/{eid}/feedback", headers=analyst_headers, json={})
    assert r.status_code == 422


def test_staff_cannot_perform_analyst_actions(client, staff_headers):
    rows = client.get("/api/emails", headers=staff_headers).json()
    eid = rows[0]["id"]
    r = client.post(f"/api/emails/{eid}/quarantine", headers=staff_headers,
                    json={"verdict": "phishing"})
    assert r.status_code == 403


def test_missing_email_returns_404(client, analyst_headers):
    assert client.get("/api/emails/999999", headers=analyst_headers).status_code == 404
