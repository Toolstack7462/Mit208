"""End-to-end smoke test for the PhishGuard API. Run while the server is up."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"


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


def main():
    ok = 0

    analyst = login("analyst@phishguard.local", "Analyst@123")
    staff = login("staff@phishguard.local", "Staff@123")
    print("[1] logins OK (analyst + staff)"); ok += 1

    s, stats = call("GET", "/api/dashboard/stats", analyst)
    assert s == 200, stats
    print(f"[2] dashboard: {stats['total_emails']} emails, "
          f"{stats['quarantined']} quarantined, {stats['confirmed_phishing']} confirmed phishing, "
          f"avg risk {stats['avg_risk_score']}, by_level={stats['by_level']}"); ok += 1

    s, emails = call("GET", "/api/emails", analyst)
    assert s == 200 and len(emails) > 0
    top = emails[0]
    print(f"[3] top email #{top['id']} score={top['risk_score']} level={top['risk_level']} status={top['status']}"); ok += 1

    # pick a safe-ish (inbox) email and a quarantined one
    inbox = next((e for e in emails if e["status"] == "inbox"), emails[-1])
    quarantined = next((e for e in emails if e["status"] == "quarantined"), top)

    s, d = call("POST", f"/api/emails/{inbox['id']}/quarantine", analyst, {"verdict": "phishing"})
    assert s == 200 and d["status"] == "quarantined", d
    print(f"[4] quarantine email #{inbox['id']} -> {d['status']}"); ok += 1

    s, d = call("POST", f"/api/emails/{inbox['id']}/release", analyst, {})
    assert s == 200 and d["status"] == "released", d
    print(f"[5] release email #{inbox['id']} -> {d['status']}"); ok += 1

    s, d = call("POST", f"/api/emails/{quarantined['id']}/confirm-phishing", analyst, {"verdict": "phishing"})
    assert s == 200 and d["status"] == "confirmed_phishing", d
    print(f"[6] confirm-phishing email #{quarantined['id']} -> {d['status']}"); ok += 1

    s, d = call("POST", f"/api/emails/{quarantined['id']}/feedback", analyst,
                {"feedback": "Confirmed credential harvesting page."})
    assert s == 200, d
    print(f"[7] submit feedback on email #{quarantined['id']} OK"); ok += 1

    # staff: only sees own mail
    s, staff_emails = call("GET", "/api/emails", staff)
    assert s == 200 and all(e["recipient"] == "staff@phishguard.local" for e in staff_emails)
    print(f"[8] staff sees only own {len(staff_emails)} emails"); ok += 1

    # staff release request
    target = next((e for e in staff_emails if e["status"] in ("quarantined", "confirmed_phishing")), staff_emails[0])
    s, req = call("POST", "/api/release-requests", staff,
                  {"email_id": target["id"], "reason": "Expected vendor invoice."})
    assert s == 201, req
    print(f"[9] staff created release request #{req['id']} status={req['status']}"); ok += 1

    # analyst approves it
    s, d = call("POST", f"/api/release-requests/{req['id']}/decision", analyst,
                {"status": "approved", "review_note": "Verified, releasing."})
    assert s == 200 and d["status"] == "approved", d
    print(f"[10] analyst approved request #{req['id']} -> {d['status']}"); ok += 1

    # staff CANNOT view audit logs (403); analyst can
    s, _ = call("GET", "/api/audit-logs", staff)
    assert s == 403, s
    s, logs = call("GET", "/api/audit-logs", analyst)
    assert s == 200 and len(logs) > 0
    actions = {}
    for l in logs:
        actions[l["action"]] = actions.get(l["action"], 0) + 1
    print(f"[11] staff blocked from audit (403); analyst sees {len(logs)} logs: {actions}"); ok += 1

    print(f"\nALL {ok}/11 CHECKS PASSED")


if __name__ == "__main__":
    main()
