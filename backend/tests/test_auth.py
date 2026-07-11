"""Authentication and role-based access-control tests."""


def test_login_success_returns_token_and_user(client):
    r = client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": "Analyst@123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "analyst"


def test_login_wrong_password_rejected(client):
    r = client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_rejected(client):
    r = client.post("/api/auth/login",
                    json={"email": "nobody@phishguard.local", "password": "x"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(client, analyst_headers):
    r = client.get("/api/auth/me", headers=analyst_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "analyst@phishguard.local"


def test_invalid_token_rejected(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_staff_cannot_reach_analyst_only_endpoints(client, staff_headers):
    # Audit log is analyst/admin only.
    assert client.get("/api/audit-logs", headers=staff_headers).status_code == 403
