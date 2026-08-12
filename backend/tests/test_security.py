"""Security-control tests: secret handling, brute-force limiting, headers, RBAC.

Covers the controls added after the audit — see docs/SECURITY.md.
"""
import pytest

from app.config import INSECURE_SECRET_PLACEHOLDER, MIN_SECRET_LENGTH, Settings
from app.routers.auth import login_limiter


# --- SECRET_KEY handling ----------------------------------------------------

def test_production_refuses_the_placeholder_secret():
    """A predictable signing key lets anyone forge an admin token, so production
    must fail to start rather than warn."""
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(environment="production", secret_key=INSECURE_SECRET_PLACEHOLDER)


def test_production_refuses_a_short_secret():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(environment="production", secret_key="tooshort")


def test_production_accepts_a_strong_secret():
    strong = "s" * (MIN_SECRET_LENGTH + 8)
    cfg = Settings(environment="production", secret_key=strong)
    assert cfg.secret_key == strong
    assert cfg.is_production is True


def test_development_substitutes_a_random_secret_instead_of_the_placeholder():
    a = Settings(environment="development", secret_key=INSECURE_SECRET_PLACEHOLDER)
    b = Settings(environment="development", secret_key=INSECURE_SECRET_PLACEHOLDER)
    assert a.secret_key != INSECURE_SECRET_PLACEHOLDER
    assert len(a.secret_key) >= MIN_SECRET_LENGTH
    assert a.secret_key != b.secret_key  # random per process, never a fixed fallback


def test_the_old_hardcoded_default_is_still_refused():
    """Regression guard: this literal used to be the built-in default."""
    with pytest.raises(ValueError):
        Settings(environment="production",
                 secret_key="dev-only-change-me-please-0123456789abcdef")


# --- Brute-force protection -------------------------------------------------

def test_repeated_failed_logins_are_rate_limited(client):
    limit = login_limiter.max_attempts
    for _ in range(limit):
        r = client.post("/api/auth/login",
                        json={"email": "analyst@phishguard.local", "password": "wrong"})
        assert r.status_code == 401
    blocked = client.post("/api/auth/login",
                          json={"email": "analyst@phishguard.local", "password": "wrong"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_rate_limit_blocks_even_a_correct_password(client):
    """Once the budget is spent the account is protected regardless of what is
    guessed next — otherwise the limiter would leak which guess was right."""
    for _ in range(login_limiter.max_attempts):
        client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": "wrong"})
    r = client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": "Analyst@123"})
    assert r.status_code == 429


def test_successful_login_clears_the_failure_counter(client):
    for _ in range(login_limiter.max_attempts - 1):
        client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": "wrong"})
    ok = client.post("/api/auth/login",
                     json={"email": "analyst@phishguard.local", "password": "Analyst@123"})
    assert ok.status_code == 200
    # counter reset, so a fresh run of failures is allowed again
    again = client.post("/api/auth/login",
                        json={"email": "analyst@phishguard.local", "password": "wrong"})
    assert again.status_code == 401


# --- Credential handling ----------------------------------------------------

def test_password_is_never_returned_by_any_auth_response(client, analyst_headers):
    login = client.post("/api/auth/login",
                        json={"email": "analyst@phishguard.local", "password": "Analyst@123"})
    me = client.get("/api/auth/me", headers=analyst_headers)
    for text in (login.text, me.text):
        assert "Analyst@123" not in text
        assert "hashed_password" not in text
        assert "$2b$" not in text  # bcrypt hash prefix


def test_passwords_are_stored_as_bcrypt_hashes():
    from app.security import hash_password, verify_password
    h = hash_password("Analyst@123")
    assert h.startswith("$2b$")
    assert h != "Analyst@123"
    assert verify_password("Analyst@123", h)
    assert not verify_password("wrong", h)


def test_unknown_and_wrong_password_are_indistinguishable(client):
    """Both must return the same status and message, or the endpoint becomes an
    account-enumeration oracle."""
    unknown = client.post("/api/auth/login",
                          json={"email": "nobody@phishguard.local", "password": "x"})
    wrong = client.post("/api/auth/login",
                        json={"email": "analyst@phishguard.local", "password": "x"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]


def test_login_is_case_insensitive_on_the_email(client):
    r = client.post("/api/auth/login",
                    json={"email": "ANALYST@PhishGuard.Local", "password": "Analyst@123"})
    assert r.status_code == 200


# --- Transport / response hardening ----------------------------------------

def test_security_headers_are_present(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_database_status_never_exposes_credentials(client):
    r = client.get("/system/database-status")
    assert r.status_code == 200
    body = r.text
    assert "password" not in body.lower()
    assert "@" not in r.json()["url_scheme"]


# --- Authorisation boundaries ----------------------------------------------

def test_expired_or_forged_token_is_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "admin@phishguard.local", "role": "admin"},
                        "an-attacker-chosen-key", algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_token_role_claim_cannot_escalate_privileges(client):
    """Role is re-read from the database on every request, so a tampered role
    claim in an otherwise perfectly valid token cannot grant analyst access."""
    from app.security import create_access_token, decode_access_token
    import jwt
    from app.config import settings

    # Start from a genuine staff token so every other claim is correct, then
    # rewrite only the role and re-sign it with the real key.
    claims = decode_access_token(create_access_token("staff@phishguard.local", "staff"))
    claims["role"] = "admin"
    escalated = jwt.encode(claims, settings.secret_key, algorithm=settings.algorithm)

    r = client.get("/api/audit-logs", headers={"Authorization": f"Bearer {escalated}"})
    assert r.status_code == 403, "a tampered role claim must not grant access"


def test_access_token_carries_identifying_claims():
    """jti and iat let an individual token be identified and aged in a log, and
    are what a future revocation list would key on."""
    from app.security import TOKEN_TYPE_ACCESS, create_access_token, decode_access_token
    claims = decode_access_token(create_access_token("analyst@phishguard.local", "analyst"))
    assert claims["typ"] == TOKEN_TYPE_ACCESS
    assert claims["sub"] == "analyst@phishguard.local"
    assert claims["jti"] and claims["iat"] and claims["exp"]


def test_each_token_has_a_unique_identifier():
    from app.security import create_access_token, decode_access_token
    a = decode_access_token(create_access_token("analyst@phishguard.local", "analyst"))
    b = decode_access_token(create_access_token("analyst@phishguard.local", "analyst"))
    assert a["jti"] != b["jti"]


def test_token_of_another_type_is_rejected(client):
    """A token minted for some other purpose must not be replayable as an access
    token, even when signed with the correct key."""
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    wrong_type = jwt.encode(
        {
            "sub": "admin@phishguard.local", "role": "admin", "typ": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        settings.secret_key, algorithm=settings.algorithm,
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {wrong_type}"})
    assert r.status_code == 401


def test_token_without_the_required_claims_is_rejected(client):
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    no_subject = jwt.encode(
        {"role": "admin", "typ": "access",
         "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
        settings.secret_key, algorithm=settings.algorithm,
    )
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {no_subject}"}).status_code == 401


def test_expired_token_is_rejected(client):
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import settings

    expired = jwt.encode(
        {"sub": "analyst@phishguard.local", "role": "analyst", "typ": "access",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.secret_key, algorithm=settings.algorithm,
    )
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {expired}"}).status_code == 401


# --- Password boundary ------------------------------------------------------

def test_password_longer_than_bcrypt_allows_is_refused_not_truncated():
    """bcrypt hashes only the first 72 bytes. Silent truncation would make two
    different long passwords interchangeable, so over-long input is refused."""
    from app.security import BCRYPT_MAX_BYTES, PasswordTooLongError, hash_password
    import pytest as _pytest

    with _pytest.raises(PasswordTooLongError):
        hash_password("A" * (BCRYPT_MAX_BYTES + 1))


def test_verify_password_never_raises_on_an_over_long_input():
    from app.security import hash_password, verify_password
    stored = hash_password("Analyst@123")
    assert verify_password("A" * 500, stored) is False


def test_login_with_an_over_long_password_is_a_validation_error(client):
    r = client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": "A" * 200})
    assert r.status_code == 422


# --- The limit is 72 BYTES, not 72 characters -------------------------------

def test_a_72_character_multibyte_password_is_rejected_at_the_boundary(client):
    """bcrypt's limit is bytes. Pydantic's max_length counts characters, so on its
    own it accepted 72 two-byte characters — 144 bytes — and the caller then got an
    opaque 401 from deeper in the stack instead of a validation error."""
    password = "é" * 72                       # 72 characters, 144 UTF-8 bytes
    assert len(password) == 72
    assert len(password.encode("utf-8")) == 144

    r = client.post("/api/auth/login",
                    json={"email": "analyst@phishguard.local", "password": password})
    assert r.status_code == 422, r.text
    assert "byte" in r.text.lower()


def test_a_multibyte_password_inside_the_byte_limit_is_accepted_by_validation():
    """The rule must bound bytes, not reject non-Latin characters outright: 30
    two-byte characters is 60 bytes and has to pass."""
    from app.schemas import LoginRequest
    password = "é" * 30                       # 60 bytes
    assert len(password.encode("utf-8")) == 60
    assert LoginRequest(email="a@b.local", password=password).password == password


def test_bcrypt_boundary_is_exact_at_72_bytes():
    from app.schemas import LoginRequest
    import pydantic
    import pytest as _pytest

    LoginRequest(email="a@b.local", password="A" * 72)          # exactly 72 bytes
    with _pytest.raises(pydantic.ValidationError):
        LoginRequest(email="a@b.local", password="A" * 71 + "é")  # 73 bytes


# --- Both sign-in routes are audited ----------------------------------------

def test_the_oauth2_token_route_is_audited_like_login(client, analyst_headers):
    """/api/auth/token mints a real access token, so leaving it unaudited made
    "every login is recorded" untrue for anyone signing in through Swagger."""
    before = len(client.get("/api/audit-logs", headers=analyst_headers).json())

    r = client.post("/api/auth/token",
                    data={"username": "analyst@phishguard.local", "password": "Analyst@123"})
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]

    logs = client.get("/api/audit-logs", headers=analyst_headers).json()
    assert len(logs) > before
    assert any(entry["action"] == "login" for entry in logs)


def test_the_api_reports_one_centralised_version(client):
    """The OpenAPI document, GET / and GET /health must not drift apart."""
    from app import __version__

    assert client.get("/").json()["version"] == __version__
    assert client.get("/health").json()["version"] == __version__
    assert client.get("/openapi.json").json()["info"]["version"] == __version__


def test_staff_cannot_read_another_users_email(client, staff_headers, analyst_headers):
    # Ingest mail addressed to a different person, then confirm staff@ cannot open it.
    other = client.post("/api/emails", headers=analyst_headers, json={
        "sender": "hr@phishguard.local", "recipient": "someone.else@phishguard.local",
        "subject": "Private HR matter", "body": "Confidential.",
    })
    assert other.status_code == 201
    r = client.get(f"/api/emails/{other.json()['id']}", headers=staff_headers)
    assert r.status_code == 403


def test_staff_cannot_see_another_users_email_in_the_list(client, staff_headers, analyst_headers):
    client.post("/api/emails", headers=analyst_headers, json={
        "sender": "hr@phishguard.local", "recipient": "someone.else@phishguard.local",
        "subject": "Private HR matter", "body": "Confidential.",
    })
    rows = client.get("/api/emails", headers=staff_headers).json()
    assert rows
    assert all(e["recipient"] == "staff@phishguard.local" for e in rows)


def test_every_protected_endpoint_requires_a_token(client):
    for method, path in [
        ("get", "/api/emails"),
        ("get", "/api/emails/1"),
        ("post", "/api/emails"),
        ("get", "/api/release-requests"),
        ("post", "/api/release-requests"),
        ("get", "/api/audit-logs"),
        ("get", "/api/dashboard/stats"),
    ]:
        r = client.post(path, json={}) if method == "post" else client.get(path)
        assert r.status_code == 401, f"{method.upper()} {path} was reachable without a token"
