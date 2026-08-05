# PhishGuard — Security and Privacy Controls

What is implemented, where it lives, how it is tested, and — just as important —
what is **not** protected. This is a student MVP running on localhost, not a
hardened production system; the limitations section is deliberately explicit.

---

## 1. Authentication

| Control | Implementation | Test |
|---|---|---|
| Passwords stored as bcrypt hashes with per-password salt | `app/security.py` — `bcrypt.hashpw(…, bcrypt.gensalt())` | `test_security.py::test_passwords_are_stored_as_bcrypt_hashes` |
| No password or hash in any API response | `UserOut` omits `hashed_password` | `test_password_is_never_returned_by_any_auth_response` |
| Stateless JWT (HS256) with expiry | `app/security.py` — `exp` from `ACCESS_TOKEN_EXPIRE_MINUTES` | `test_expired_token_is_rejected` |
| Tokens carry `iat`, `jti` and `typ` | `app/security.py` — a token of another type is refused, `exp`/`sub` required, algorithm allow-listed | `test_access_token_carries_identifying_claims`, `test_token_of_another_type_is_rejected` |
| Over-long passwords refused, never truncated | `app/security.py` — `PasswordTooLongError` above bcrypt's 72-byte limit | `test_password_longer_than_bcrypt_allows_is_refused_not_truncated` |
| Concurrent duplicate request answered correctly | `routers/requests.py` — an index violation becomes 409, not a 503 that advises a retry which cannot succeed | `test_a_concurrent_duplicate_request_gets_409_not_503` |
| Wrongly-signed tokens rejected | `jwt.decode` verifies the signature; any `PyJWTError` → 401 | `test_expired_or_forged_token_is_rejected` |
| No account enumeration | Unknown address and wrong password return an identical 401 and message | `test_unknown_and_wrong_password_are_indistinguishable` |
| No timing-based enumeration | `dummy_verify()` burns one bcrypt comparison when the address is unknown | reviewed; timing is not asserted numerically (see limitations) |
| Brute-force limiting | `app/ratelimit.py` — per-IP failed-attempt window → 429 + `Retry-After` | `test_repeated_failed_logins_are_rate_limited`, `test_rate_limit_blocks_even_a_correct_password` |
| Deactivated accounts locked out immediately | `is_active` checked at login **and** on every authenticated request | `test_login_success_returns_token_and_user`, `deps.get_current_user` |
| Case-insensitive login | Address normalised to lowercase before lookup | `test_login_is_case_insensitive_on_the_email` |

---

## 2. Authorisation

Three roles: `analyst`, `staff`, `admin`.

| Control | Implementation | Test |
|---|---|---|
| Role guard on protected routes | `deps.require_roles(*roles)` dependency factory | `test_auth.py::test_staff_cannot_reach_analyst_only_endpoints` |
| **Role is never taken from the token** | `get_current_user` decodes only `sub`, then re-reads the user row; the `role` claim is not trusted | `test_security.py::test_token_role_claim_cannot_escalate_privileges` |
| Staff see only their own mail | `recipient == current.email` filter applied server-side in the query | `test_staff_only_sees_own_mail`, `test_staff_cannot_see_another_users_email_in_the_list` |
| Staff cannot open another user's email by id | Ownership re-checked in `get_email` | `test_staff_cannot_read_another_users_email` |
| Staff cannot perform analyst actions | `ANALYST = require_roles("analyst", "admin")` | `test_staff_cannot_perform_analyst_actions` |
| Staff cannot read the audit log | `VIEWER = require_roles("analyst", "admin")` | `test_staff_cannot_reach_analyst_only_endpoints` |
| Staff cannot decide release requests | `REVIEWER = require_roles("analyst", "admin")` | `test_staff_cannot_decide_requests` |
| Staff see only their own requests | `requested_by == current.id` filter | `test_staff_sees_only_their_own_requests` |
| Dashboard figures are role-scoped | Same recipient filter applied to every aggregate | `test_dashboard_stats_shape` |
| No endpoint reachable without a token | — | `test_every_protected_endpoint_requires_a_token` (7 endpoints) |

**The frontend route guards in `App.jsx` are a usability feature, not a security
control.** Every restriction is enforced again server-side, which is what the
tests assert.

---

## 3. Input validation

Constraints live in `app/schemas.py` and mirror the column widths in
`database/schema.sql`, so behaviour is identical on SQLite and PostgreSQL.

| Field | Rule |
|---|---|
| `sender`, `recipient` | required, valid address form, ≤ 320, lowercased |
| `sender_name` | ≤ 255 |
| `subject` | ≤ 500 |
| `body` | ≤ 100 000 |
| `reason` (release request) | required, 10–2000 chars after trimming |
| `verdict` | ≤ 32 |
| `feedback` | ≤ 2000; whitespace-only treated as absent |
| `decision.status` | `Literal["approved", "denied"]` |
| `login.password` | 1-72 chars (bcrypt's input limit) |
| `audit_logs.limit` | ≤ 1000 |

The database enforces the same value sets independently: `CHECK` constraints on
`role`, email `status`, `risk_level`, the SPF/DKIM/DMARC columns and
`risk_score BETWEEN 0 AND 100`, a constraint requiring a decided release request
to record its reviewer, and a partial unique index making "one pending request
per user per email" atomic. See `docs/BUG_LOG.md`, BUG-13.

Rejected input returns `422` with a field-level list. See `docs/BUG_LOG.md`
BUG-03 for why this matters more than it appears.

---

## 4. Injection and output handling

| Risk | Position |
|---|---|
| **SQL injection** | Every query uses the SQLAlchemy ORM with bound parameters. No string-concatenated SQL exists anywhere in `backend/app/`. |
| **LIKE wildcard abuse** | `%`, `_` and `\` are escaped in the search term and `escape="\\"` is passed to `ilike` (BUG-09). |
| **Stored XSS via email body** | Email bodies are attacker-controlled by definition. They are rendered as **text**, never with `dangerouslySetInnerHTML` — verified absent from the codebase — so React escapes them. |
| **Response-type confusion** | `X-Content-Type-Options: nosniff` and a `default-src 'none'` CSP on API responses. |
| **Clickjacking** | `X-Frame-Options: DENY` and `frame-ancestors 'none'`. |
| **CORS** | Explicit origin allow-list from `FRONTEND_ORIGIN`; not a wildcard. |

---

## 5. Secret management

| Control | Implementation |
|---|---|
| No secrets in version control | `backend/.env` and `frontend/.env` are in `.gitignore`; only `.env.example` is committed |
| `.env.example` contains no working values | Placeholder `SECRET_KEY`, and `DATABASE_URL` uses literal `USER:PASSWORD` |
| Weak signing keys refused | `config.py` rejects the placeholder, the previous hard-coded default, and anything under 32 chars — fatal in production, random substitute + warning in development (BUG-05) |
| Credentials never exposed by an endpoint | `/system/database-status` returns the URL **scheme only** — tested by `test_database_status_never_exposes_credentials` |
| Internal detail withheld in production | The catch-all handler includes exception text only when `ENVIRONMENT != production` |
| Tracebacks never sent to clients | Full traceback goes to the server log; the client gets a generic message plus `request_id` |

---

## 6. Auditability

Every state-changing operation writes one `audit_logs` row via
`app/audit.py::record_audit`, inside the same transaction as the change itself —
so an action and its audit entry commit or roll back together.

Recorded: actor id, actor email (denormalised so it survives user changes),
action, entity type and id, human-readable detail, client IP, UTC timestamp.

Actions covered: `login`, `ingest_email`, `quarantine`, `release`,
`confirm_phishing`, `feedback`, `release_request_created`,
`release_request_approved`, `release_request_denied`.

The table is append-only — no route updates or deletes an audit row. Reads are
restricted to analyst/admin.

Tested by `test_requests_audit.py::test_actions_are_audited` and
`test_release_workflow.py::test_approval_records_an_analyst_review_and_audit_entry`.

---

## 7. Privacy

- **No real email data.** All 8 sample messages in `backend/app/seed.py` are
  synthetic, written for this project.
- **No real addresses.** Every demo account uses the reserved, non-routable
  `.local` domain, so no address can resolve to a real mailbox.
- **No real credentials.** The demo passwords exist only in the seed script and
  the README, and are stored as bcrypt hashes.
- **No external transmission.** The application makes no outbound network calls;
  nothing is sent to a third-party service.
- **Look-alike domains are deliberately misspelled** (`paypa1-support.com`,
  `micros0ft-alerts.com`) so no sample references a real company's domain.
- **SPF/DKIM/DMARC results are simulated** from the rule engine's own signals —
  the synthetic dataset contains no real SMTP headers. This is labelled in the
  UI, the API docs and the report rather than presented as real verification.

---

## 8. Known limitations

Stated plainly; none is claimed as solved.

1. **JWT in `localStorage`.** Readable by any script that achieves XSS. An
   `HttpOnly` cookie would be better but requires CSRF protection and a
   same-site deployment. Accepted for a localhost MVP.
2. **Rate-limit state is per-process.** `app/ratelimit.py` uses in-memory
   counters, so with multiple Uvicorn workers each keeps its own budget and the
   effective limit multiplies. A shared store (Redis) is needed for a real
   deployment. The single-worker demo is unaffected.
3. **No HTTPS.** The demo runs over plain HTTP on localhost, so tokens are not
   encrypted in transit. Any real deployment must terminate TLS.
4. **No token revocation.** JWTs are stateless and valid until `exp`. Logout
   clears the client copy only; a stolen token stays valid until it expires.
   Deactivating the account does block it, because `is_active` is re-checked per
   request.
5. **No password policy or rotation.** There is no self-service registration or
   password change; accounts come from the seed script.
6. **No account lockout.** Rate limiting is per **IP**, not per account, so a
   distributed attacker with many source addresses is not slowed.
7. **Timing equalisation is best-effort.** `dummy_verify` makes the two login
   paths comparable but not provably constant-time, and no test asserts a timing
   bound.
8. **No CSRF protection.** Not currently required — authentication is a `Bearer`
   header, not a cookie — but it would become necessary if the token ever moved
   to a cookie.
9. **`status`/`role`/`risk_level` are unconstrained at the database level.** The
   API validates them, but a direct SQL write could store an unknown value.
10. **No dependency vulnerability scanning in CI.** Dependencies are pinned to
    compatible-release ranges and were installed successfully, but no automated
    audit step runs. `pip-audit` / `npm audit` in CI is future work.
11. **The rule engine is heuristic.** It will produce false positives (an urgent
    but genuine internal notice) and false negatives (a well-written spear-phish
    with no keyword triggers). Human review is the control, which is exactly why
    the quarantine/release workflow exists. No accuracy metric is claimed,
    because the project has no labelled evaluation corpus.

---

## 9. Standards referenced

Reviewed against the OWASP Top 10 (2021/2025 draft) categories relevant to this
application:

| Category | Position |
|---|---|
| A01 Broken Access Control | Addressed — server-side role guards + per-record ownership checks; role never read from the token |
| A02 Cryptographic Failures | Partly — bcrypt hashing and enforced signing-key strength; **no HTTPS** in the local demo |
| A03 Injection | Addressed — ORM-bound parameters throughout; no `dangerouslySetInnerHTML` |
| A04 Insecure Design | Addressed for the core workflow — state-transition guards, one-open-request rule, append-only audit |
| A05 Security Misconfiguration | Addressed — weak `SECRET_KEY` refused, no secrets committed, security headers set, CORS allow-listed |
| A07 Identification & Authentication Failures | Partly — brute-force limiting, no enumeration, immediate deactivation; **no MFA, no revocation** |
| A08 Software & Data Integrity Failures | Partly — dependencies pinned to compatible ranges; **no automated vulnerability scan** |
| A09 Logging & Monitoring Failures | Addressed for auditing — every action logged with actor, entity and IP; **no alerting** |
