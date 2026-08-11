# PhishGuard — System Architecture

This document describes the architecture of the system **as implemented**. Every
component named here exists in the repository at the path given.

---

## 1. High-level architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  BROWSER (http://localhost:5173)                                         │
│                                                                          │
│  React 18 SPA (Vite)                                                     │
│  ├── pages/      Login · Dashboard · Inbox · StaffPortal ·               │
│  │               ReleaseRequests · AuditLogs                             │
│  ├── context/    AuthContext — holds the session, exposes login/logout    │
│  ├── components/ Layout · Sidebar · RiskBadge · EmailDetailPanel ·        │
│  │               Donut · BarChart · StateBlock (loading/error/empty) ·    │
│  │               Toast (success/error notifications)                      │
│  └── lib/        risk.js (level → UI category) · errors.js (API error →   │
│                  user-facing message)                                     │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  HTTPS/HTTP + JSON
                                │  Authorization: Bearer <JWT>
                                │  (axios interceptor, src/api.js)
┌───────────────────────────────▼──────────────────────────────────────────┐
│  BACKEND API (http://localhost:8000) — FastAPI + Uvicorn                  │
│                                                                          │
│  main.py       app assembly · CORS · security headers · request-id       │
│                middleware · global exception handlers (error envelope)    │
│                                                                          │
│  routers/      auth.py      POST /api/auth/login, /token · GET /me        │
│                emails.py    list/detail/ingest + analyst actions          │
│                requests.py  staff release requests + analyst decisions    │
│                audit.py     read-only audit trail (analyst/admin)         │
│                dashboard.py aggregate statistics                          │
│                                                                          │
│  deps.py       get_current_user (JWT → DB user) · require_roles(...)      │
│  schemas.py    Pydantic v2 request/response models + input constraints    │
│  transitions.py  the email state machine — which action is valid from     │
│                which status; imported by emails.py AND requests.py, and    │
│                mirrored by frontend/src/lib/transitions.js                 │
│  scoring.py    rule-based risk engine (pure function, no I/O)             │
│  security.py   bcrypt hashing (72-byte guard) · typed JWT encode/decode   │
│  ratelimit.py  per-IP failed-login limiter                                │
│  audit.py      append-only audit helper                                   │
│  config.py     env-driven settings + SECRET_KEY enforcement               │
│  ml_model.py   documented integration point — NOT wired in (see below)    │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │  SQLAlchemy 2.0 ORM
┌───────────────────────────────▼──────────────────────────────────────────┐
│  DATABASE — PostgreSQL 14+ (official target)                             │
│              SQLite (zero-install fallback for quick local testing)       │
│                                                                          │
│  users · email_records · analyst_reviews ·                               │
│  staff_release_requests · audit_logs                                     │
│                                                                          │
│  CHECK constraints on every enumerated column, risk_score bounded 0-100,  │
│  and a PARTIAL UNIQUE INDEX enforcing one pending release request per     │
│  (email, requester) — atomic, unlike an application-level check.          │
│                                                                          │
│  Reference DDL: database/schema.sql                                      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Note on the ML component.** `backend/app/ml_model.py` is a documented
placeholder for a future DistilBERT classifier. It is **not** part of the MVP and
is **not** called by any running code path. All risk scores in the working system
come from the rule engine in `scoring.py`. This is stated here, in the README and
in the report so the boundary between what is built and what is planned is
unambiguous.

---

## 2. Core end-to-end workflow

The primary user journey — the one demonstrated in the walkthrough — is:

```
 1. INGESTION
    POST /api/emails (analyst/admin)
        └─> scoring.score_email(sender, subject, body, sender_name)
              returns score 0-100, level, list of human-readable reasons,
              simulated SPF/DKIM/DMARC, AI-generated flag
        └─> level in {high, critical} ? status = "quarantined"
                                      : status = "inbox"
        └─> INSERT email_records
        └─> INSERT audit_logs (action = "ingest_email")

 2. ANALYST REVIEW
    GET  /api/emails            -> risk-sorted list
    GET  /api/emails/{id}       -> body + reasons + auth results
    POST /api/emails/{id}/quarantine | release | confirm-phishing | feedback
        └─> transitions.is_allowed(action, email.status)?  409 if not
        └─> INSERT analyst_reviews
        └─> UPDATE email_records.status  (rejected with 409 if unchanged)
        └─> INSERT audit_logs

 3. STAFF RELEASE REQUEST
    GET  /api/emails            -> staff see ONLY mail addressed to them
    POST /api/release-requests  (STAFF ONLY, own mail only; reason >= 10 chars;
                                 email must be held; one open request per user)
        └─> INSERT staff_release_requests (status = "pending")
        └─> INSERT audit_logs

 4. ANALYST DECISION
    POST /api/release-requests/{id}/decision  {approved|denied}
        └─> approved ? transitions.is_allowed("release", email.status)? 409 if not
        └─> UPDATE staff_release_requests (status, reviewer, note, timestamp)
        └─> approved ? UPDATE email_records.status = "released"
                       + INSERT analyst_reviews
        └─> INSERT audit_logs

 5. OVERSIGHT
    GET /api/audit-logs         -> analyst/admin only
    GET /api/dashboard/stats    -> role-scoped aggregate counts
```

---

## 3. Request lifecycle

Every API request passes through the same chain:

```
Request
  │
  ├─ CORS middleware ................. origin allow-list from FRONTEND_ORIGIN
  ├─ request-id / security headers ... X-Request-ID, nosniff, DENY, CSP
  ├─ Route match ..................... FastAPI router
  ├─ Pydantic validation ............. schemas.py — 422 on bad input
  ├─ Depends(get_current_user) ....... JWT decoded, user re-loaded from DB
  ├─ Depends(require_roles(...)) ..... 403 if the role is not permitted
  ├─ Handler ......................... business logic + DB session
  └─ Response / exception handler .... consistent error envelope
```

### The email state machine

`app/transitions.py` is the only place the workflow rules are written down. Both
paths that can move an email import it, so they cannot disagree:

| Action | Valid from | Moves to |
|---|---|---|
| `quarantine` | `inbox`, `released`, `safe` | `quarantined` |
| `release` | `quarantined`, `confirmed_phishing` | `released` |
| `confirm_phishing` | every status except itself | `confirmed_phishing` |
| `feedback` | any status | *(no change)* |

`quarantine` is deliberately **not** valid from `confirmed_phishing`: that would
replace a stronger verdict with a weaker one. `HOLDABLE_STATUSES` — the states a
staff release request may be raised from — is *derived* from the `release` row
rather than declared separately, so the action and the request rule stay in step.

`frontend/src/lib/transitions.js` mirrors the same table so the interface only
offers transitions the API will accept. Because a mirror can drift,
`tests/test_transitions.py::test_the_frontend_mirror_matches_the_backend_rules`
reads the JavaScript file and compares it with the Python one.

**Authorisation is never taken from the token.** `get_current_user` decodes the
JWT only to obtain the subject (email), then re-reads the user row from the
database. The `role` claim in the token is not trusted for access decisions, so a
tampered token cannot escalate privileges. This is covered by
`tests/test_security.py::test_token_role_claim_cannot_escalate_privileges`.

---

## 4. Error envelope

All errors share one shape, produced by the handlers in `main.py`:

```json
{
  "error": {
    "code": 409,
    "message": "You already have a pending release request for this email.",
    "details": null,
    "request_id": "0f2c…"
  }
}
```

| Situation                        | Status | Source                          |
|----------------------------------|--------|---------------------------------|
| Deliberate rejection             | 4xx    | `StarletteHTTPException` handler|
| Invalid input                    | 422    | `RequestValidationError` handler|
| Database fault / constraint      | 503    | `SQLAlchemyError` handler       |

A handler that raises part-way through a multi-row change is rolled back by
`database.session_scope`, so a failed request writes nothing at all. The test suite
binds that same function to its own engine, so the behaviour under test is the real
implementation rather than a copy.
| Anything unforeseen              | 500    | catch-all `Exception` handler   |

The frontend reads this through `src/lib/errors.js`, so a failure always becomes
a sentence the user can act on. `request_id` is echoed in the `X-Request-ID`
header and written to the server log, so a user-reported error can be traced.

---

## 5. Key design decisions

| Decision | Reason |
|---|---|
| **Rule engine, not ML, for the MVP** | Every point of the score comes with a human-readable reason. An analyst can see *why* a message was flagged, which matters more in a review tool than raw accuracy — and it is explainable in a code review. |
| **JWT (stateless) over server sessions** | The backend is a pure API consumed by a separate SPA origin. No session store to run, and the Swagger UI can authenticate with the same mechanism. |
| **Role re-read from the DB per request** | Keeps the token a *claim of identity* only, never a *grant of authority*. Deactivating a user takes effect immediately instead of at token expiry. |
| **PostgreSQL primary, SQLite fallback** | PostgreSQL is the assessed target; the SQLite fallback means the project can be demonstrated on any machine with no database installation. The ORM uses no engine-specific features. |
| **Validation constraints mirror column widths** | SQLite silently accepts over-long strings but PostgreSQL rejects them. Validating at the API boundary makes behaviour identical on both engines (see `docs/BUG_LOG.md`, BUG-03). |
| **Rules enforced in the API *and* the database** | The API gives a clear 4xx with a readable message; the `CHECK` constraints and the partial unique index make the same rules hold against a direct SQL write and against two concurrent requests, which an application-level check alone cannot do (BUG-13). |
| **Stored data parsed defensively** | The score and level live in their own columns, so a corrupt explanation should degrade to a placeholder rather than cost access to the whole record (BUG-12). |
| **Application-level append-only audit log** | There is no update or delete path for `audit_logs` in the application. Every state change writes one row with actor, entity, detail and IP. This is not immutable storage: direct SQL access could still alter the table. |
| **In-process rate limiter** | Adequate for the single-worker demo this project targets and dependency-free. Its multi-worker limitation is stated in `docs/SECURITY.md` rather than hidden. |
