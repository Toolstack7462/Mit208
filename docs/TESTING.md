# PhishGuard — Test Strategy, Evidence and Results

Every figure below was produced by running the commands shown, on this
repository, on **12 August 2026** as part
of the final documentation audit. Nothing here is estimated.

**Environment:** Windows 11, Python 3.14.3, Node.js 24.14.1, PostgreSQL 16.6.
The suite runs on in-memory SQLite by default and on PostgreSQL when
`TEST_DATABASE_URL` is set; both were run for this record, as was the
`backend-postgres` CI job.

---

## 1. Summary

| Layer | Tool | Files | Tests | Result |
|---|---|---|---|---|
| Backend unit + API (SQLite) | pytest 9.1.1 | 9 | **175** | **175 passed** |
| Backend unit + API (**PostgreSQL 16.6**) | pytest 9.1.1 | 9 | **175** | **175 passed** |
| Frontend unit + component | vitest 2.1.9 | 11 | **92** | **92 passed** |
| Live end-to-end (running server) | `smoke_test.py` | 1 | **22 checks** | **22/22 passed** |
| Production build | `vite build` | — | — | **built in 16.70s**, 1655 modules |
| Secret scan | `evidence/secret_scan.py` | every tracked file | — | **0 unacknowledged findings** |
| **Total automated** | | **20** | **267** | **267 passed, 0 failed** |

**Backend statement coverage: 90% (861 of 953 statements).**

The backend suite was run twice — once on in-memory SQLite and once against a
real PostgreSQL 16.6 server — and passes identically on both. That is what
substantiates the claim that the two engines behave the same; running only on
SQLite would not (see BUG-03 and BUG-16, both of which are engine-specific).

---

## 2. How to reproduce

```bash
# Backend — 175 tests, no server or database needed (in-memory SQLite)
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1     # or: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                                        # 175 passed (SQLite)

# The same suite against PostgreSQL, which is the assessed target:
#   createdb phishguard_test
#   $env:TEST_DATABASE_URL="postgresql+psycopg2://USER:PASS@localhost:5432/phishguard_test"
#   python -m pytest                                      # 175 passed (PostgreSQL)
python -m pytest --cov=app --cov-report=term-missing    # + coverage

# Frontend — 92 tests
cd ../frontend
npm install
npm test                                                # 92 passed
npm run build                                           # production build

# Live end-to-end — 22 checks against a real server
cd ../backend
python -m app.seed --reset
uvicorn app.main:app --port 8000        # in one terminal
python smoke_test.py                    # in another -> ALL 22/22 CHECKS PASSED

# Secret scan — every tracked file, standard library only, exits 1 on a finding
cd ..
python evidence/secret_scan.py          # -> SECRET SCAN CLEAN
```

---

## 3. Backend suite — 175 tests, run on both engines

| File | Tests | Covers |
|---|---|---|
| `tests/test_scoring.py` | 6 | Rule engine in isolation: benign vs phishing, brand impersonation, raw-IP links, 0–100 bound, level thresholds |
| `tests/test_auth.py` | 7 | Login success/failure, token required, `/me`, invalid token, role boundary |
| `tests/test_emails.py` | 9 | Listing, risk sort order, staff isolation, detail + reasons, status transitions, 404 |
| `tests/test_requests_audit.py` | 7 | Request creation, approval releases the email, double-decision conflict, dashboard shape, audit trail |
| `tests/test_validation.py` | 13 | Input validation, boundary lengths, unique message ids, LIKE escaping, error envelope |
| `tests/test_security.py` | 32 | Secret-key enforcement, rate limiting, credential handling, privilege escalation, token claims and types, the bcrypt 72-**byte** boundary including multibyte passwords, auditing of the OAuth2 token route, the single reported version, security headers |
| `tests/test_release_workflow.py` | 14 | Duplicate suppression, justification rules, held-only rule, decision path |
| `tests/test_integrity.py` | 35 | Defensive parsing of stored data, database CHECK constraints, the partial unique index, decision-completeness, transaction rollback, and the concurrent-duplicate race |
| `tests/test_transitions.py` | 52 | The email state machine (BUG-17) and the staff-only release-request rule (BUG-18): the rule table itself, every permitted and refused transition over the API, no write on a refusal, the frontend mirror agreeing with the backend, ownership enforcement, and approval of a stale request |

Each test runs against a **freshly created and seeded database** (`tests/conftest.py`),
so cases are independent regardless of order and the real `phishguard.db` is
never touched. The engine defaults to in-memory SQLite for speed; setting
`TEST_DATABASE_URL` runs the identical suite against PostgreSQL, and the run
header states which engine was used. The login rate limiter is reset between tests
because its state is process-wide.

### Coverage by module

```
Name                       Stmts   Miss  Cover
----------------------------------------------
app/__init__.py                1      0   100%
app/audit.py                   7      0   100%
app/config.py                 32      0   100%
app/database.py               19      1    95%
app/deps.py                   28      2    93%
app/main.py                   87      4    95%
app/ml_model.py                3      3     0%   <- unimplemented placeholder
app/models.py                 86      0   100%
app/ratelimit.py              35      1    97%
app/routers/__init__.py        0      0   100%
app/routers/audit.py          14      1    93%
app/routers/auth.py           55      1    98%
app/routers/dashboard.py      26      3    88%
app/routers/emails.py        108      3    97%
app/routers/requests.py       80      1    99%
app/schemas.py               166      7    96%
app/scoring.py               101      5    95%
app/security.py               32      0   100%
app/seed.py                   60     60     0%   <- CLI script, exercised by smoke test
app/transitions.py            13      0   100%
----------------------------------------------
TOTAL                        953     92    90%
```

The two 0% modules are honest exclusions: `ml_model.py` is a documented
placeholder that is deliberately not wired in, and `seed.py` is a command-line
script covered by the live smoke test instead. Excluding those two, coverage of
the running application code is **97%** (861 of 890 statements).

---

## 4. Frontend suite — 92 tests

| File | Tests | Covers |
|---|---|---|
| `src/lib/transitions.test.js` | 7 | The mirrored state machine: release only from a held status, quarantine never downgrading a phishing verdict, feedback valid everywhere, no self-targeting transition, tooltip wording |
| `src/components/EmailDetailPanel.test.jsx` | 16 | Which action buttons are enabled for each of the five statuses, in both analyst and staff mode; a disabled action does not fire; a permitted one does; the busy state |
| `src/lib/errors.test.js` | 13 | Error-message mapping: API envelope, FastAPI `detail`, validation list, unreachable backend, timeout, 403/429/500, never-empty guarantee |
| `src/lib/risk.test.js` | 7 | Risk level → UI category, unknown level, metadata completeness, date formatting |
| `src/App.test.jsx` | 10 | Route protection and role-based access for all three roles |
| `src/pages/Login.test.jsx` | 7 | Form rendering, success path, wrong password, rate-limit message, unreachable API, stale-error clearing, password masking |
| `src/pages/AuditLogs.test.jsx` | 6 | Data rendering, loading state, **error vs empty distinction**, request-id display, retry |
| `src/pages/StaffPortal.test.jsx` | 7 | Mailbox listing, load failure, reason validation, trimmed submission, server rejection in-dialog, duplicate short-circuit |
| `src/pages/Dashboard.test.jsx` | 5 | Statistics rendering, loading state, **escape from the permanent-spinner bug**, retry recovery, missing `by_level` |
| `src/pages/ReleaseRequests.test.jsx` | 6 | Queue rendering, load failure, empty-vs-failure distinction, approval call, 409 surfaced, decision controls hidden from staff |
| `src/components/Toast.test.jsx` | 8 | Success vs error tone and ARIA role, timer cancellation, dismissal timing |

Component tests use `@testing-library/react` with a mocked `api` module, so they
assert real rendered output and user interaction rather than implementation
detail. Queries use accessible roles and labels (`getByRole`, `getByLabelText`),
which means a regression in labelling breaks a test.

---

## 5. Live end-to-end evidence — 22/22

Actual captured output of `python smoke_test.py` against a running Uvicorn server
backed by **PostgreSQL 16.6** with a freshly seeded database:

```
[1] health OK - engine=postgresql connected=True
[2] logins OK (analyst + staff)
[3] wrong password rejected (401): 'Incorrect email or password'
[4] unauthenticated request rejected (401)
[5] dashboard: 8 emails, 3 quarantined, 1 confirmed phishing, avg risk 41.5,
    by_level={'low': 3, 'medium': 1, 'high': 3, 'critical': 1}
[6] top email #1 score=100 level=critical status=confirmed_phishing
[7] detail #1 explains its score with 6 indicator(s)
[8] ingested phishing email #9 scored 80 (critical) and was auto-quarantined
[9] blank sender/recipient rejected (422): 'sender: String should have at least 3
    characters; recipient: String should have at least 3 characters'
[10] over-length subject rejected at the API boundary (422, not a DB 500)
[11] malformed sender address rejected (422)
[12] quarantine email #5 -> quarantined
[13] repeating the same action rejected (409): "Email is already 'quarantined'; no action taken."
[14] release email #5 -> released
[15] feedback accepted with text, rejected when blank (422)
[16] staff sees only their own 6 emails
[17] staff blocked from analyst actions and the audit log (403)
[18] release request without an adequate reason rejected (422)
[19] release request #2 created; duplicate rejected (409): 'You already have a
     pending release request for this email.'
[20] approval released email #1 and was audited; 10 log entries:
     {'release_request_approved': 1, 'release_request_created': 2, 'feedback': 1,
      'release': 1, 'quarantine': 1, 'ingest_email': 1, 'login': 2, 'confirm_phishing': 1}
[21] releasing email #10 that was never held rejected (409) and it stayed 'inbox':
     "Cannot 'release' an email with status 'inbox'. This action applies only to
      email in: quarantined, confirmed_phishing."
[22] analyst blocked from raising a staff release request (403): 'Requires role: staff'

ALL 22/22 CHECKS PASSED
```

This is the strongest single piece of integration evidence in the project: one
script drives the frontend's exact HTTP contract against a real Uvicorn server
and a real database file, and covers the complete workflow from ingestion through
scoring, analyst action, staff request, analyst decision and audit.

---

## 6. Representative test cases

Mapped to the rubric's minimum testing areas.

### Core functionality (positive path)

| ID | Feature | Action | Expected | Actual | Status |
|---|---|---|---|---|---|
| TC01 | Login | Correct analyst credentials | 200 + JWT + role `analyst` | As expected | Pass |
| TC02 | Scoring | Ingest credential-phishing email | score ≥ 50, level high/critical, ≥ 3 reasons | 80, `critical`, 5 reasons | Pass |
| TC03 | Scoring | Ingest benign newsletter | level `low`, score < 25 | As expected | Pass |
| TC04 | Auto-quarantine | Ingest a critical email | `status = quarantined` | As expected | Pass |
| TC05 | Inbox | List as analyst | Sorted by risk descending | As expected | Pass |
| TC06 | Detail | Open an email | Body + reasons + SPF/DKIM/DMARC | As expected | Pass |
| TC07 | Analyst action | Quarantine then release | `quarantined` → `released` | As expected | Pass |
| TC08 | Analyst action | Confirm phishing | `confirmed_phishing` | As expected | Pass |
| TC09 | Staff request | Submit with a valid reason | 201, `pending` | As expected | Pass |
| TC10 | Analyst decision | Approve | Request `approved`, email `released` | As expected | Pass |
| TC11 | Audit | After any action | Row with actor, entity, detail, IP | As expected | Pass |
| TC12 | Dashboard | Load as analyst | Counts, `by_level`, average | 8 / 3 / 1, avg 41.5 | Pass |

### Validation (invalid / missing input)

| ID | Input | Expected | Actual | Status |
|---|---|---|---|---|
| TC13 | Blank sender and recipient | 422 naming both fields | As expected | Pass |
| TC14 | `sender = "not-an-email"` | 422 "must be a valid email address" | As expected | Pass |
| TC15 | 501-character subject | 422, **not** 500 | As expected | Pass |
| TC16 | Exactly 500-character subject | 201 (boundary accepted) | As expected | Pass |
| TC17 | Release reason `""` | 422 | As expected | Pass |
| TC18 | Release reason `"          "` | 422 (whitespace ≠ text) | As expected | Pass |
| TC19 | Feedback `"     "` | 422 | As expected | Pass |
| TC20 | `decision.status = "maybe"` | 422 | As expected | Pass |

### Error handling

| ID | Scenario | Expected | Actual | Status |
|---|---|---|---|---|
| TC21 | Non-existent email id | 404 in the error envelope | As expected | Pass |
| TC22 | Decide an already-decided request | 409 "Request already decided" | As expected | Pass |
| TC23 | Repeat an action that changes nothing | 409, no extra audit row | As expected | Pass |
| TC24 | Duplicate pending release request | 409 | As expected | Pass |
| TC25 | Release request on a delivered email | 409 "not being held" | As expected | Pass |
| TC25a | Release an email that was never held | 409 naming the valid source states; status unchanged; no review or audit row written | As expected | Pass |
| TC25b | Quarantine an email already `confirmed_phishing` | 409 — the verdict is not downgraded | As expected | Pass |
| TC25c | Approve a release request after the email was released elsewhere | 409; the request stays `pending` | As expected | Pass |
| TC25d | Deny that same stale request | 200 — denial changes no email status, so it stays available | As expected | Pass |
| TC26 | **Backend unreachable (frontend)** | Visible error + retry, **not** an empty table | As expected | Pass |
| TC27 | 503 with a request id (frontend) | Message + traceable reference shown | As expected | Pass |
| TC28 | Every error response | Consistent envelope + `X-Request-ID` | As expected | Pass |

### Integration

| ID | Scenario | Expected | Actual | Status |
|---|---|---|---|---|
| TC29 | Frontend → API → DB → response | Full workflow over HTTP | 22/22 smoke checks | Pass |
| TC30 | Approval propagates across tables | Request, email status and audit all updated | As expected | Pass |
| TC31 | Score reasons survive the JSON round-trip | Stored as JSON, returned as a list | As expected | Pass |
| TC32 | Seed against real PostgreSQL | 4 users, 8 emails | Asserted in the `backend-postgres` CI job | Pass (CI) |

### Security / privacy

| ID | Scenario | Expected | Actual | Status |
|---|---|---|---|---|
| TC33 | Any protected endpoint, no token | 401 (7 endpoints checked) | As expected | Pass |
| TC34 | Token signed with an attacker's key | 401 | As expected | Pass |
| TC35 | Valid token with a tampered `role: admin` | 403 — role re-read from the DB | As expected | Pass |
| TC36 | Staff requests another user's email | 403 | As expected | Pass |
| TC36a | Analyst or admin raises a release request | 403 — creation is staff-only | As expected | Pass |
| TC36b | Analyst reads the release-request queue | 200 — review access is unaffected | As expected | Pass |
| TC37 | Staff reads the audit log | 403 | As expected | Pass |
| TC38 | Unknown vs wrong password | Identical status and message | As expected | Pass |
| TC39 | 11 failed logins from one IP | 429 + `Retry-After` | As expected | Pass |
| TC40 | Successful login after failures | Counter cleared | As expected | Pass |
| TC41 | Placeholder `SECRET_KEY` in production | Startup refused | As expected | Pass |
| TC42 | Any auth response | No password, hash or `$2b$` prefix | As expected | Pass |
| TC43 | `/system/database-status` | Scheme only, no credentials | As expected | Pass |
| TC44 | Response headers | `nosniff`, `DENY`, `no-referrer` | As expected | Pass |

### Usability / accessibility

| ID | Scenario | Expected | Actual | Status |
|---|---|---|---|---|
| TC45 | Login fields | Reachable by accessible label | As expected | Pass |
| TC46 | Password field | `type="password"` | As expected | Pass |
| TC47 | Error banners | `role="alert"` | As expected | Pass |
| TC48 | Reason textarea | Labelled, `aria-invalid`, counter | As expected | Pass |
| TC49 | Submit with an inadequate reason | Button disabled + inline reason | As expected | Pass |
| TC50 | Loading state | `role="status"` announced | As expected | Pass |

### Regression

| ID | Guards against | Test |
|---|---|---|
| TC51 | BUG-05 returning — the old hard-coded secret | `test_the_old_hardcoded_default_is_still_refused` |
| TC52 | BUG-04 returning — failure shown as empty | `shows an error instead of a misleading empty table…` + `shows the genuine empty state…` |
| TC53 | BUG-01 returning — uninstallable pins | CI matrix on Python 3.11 / 3.12 / 3.13 |
| TC54 | BUG-03 returning — DB-only truncation | `test_oversized_subject_rejected_not_500` + `backend-postgres` CI job |
| TC55 | Normal search still works after BUG-09 | `test_search_finds_a_known_subject` |
| TC56 | BUG-17 returning — an action accepted from an invalid source state | `test_releasing_an_email_that_was_never_held_is_refused`, `test_quarantine_cannot_downgrade_a_confirmed_phishing_verdict`, `test_a_refused_transition_writes_no_review_and_no_audit_entry` |
| TC57 | BUG-17 returning in the interface — a button offering an invalid action | `EmailDetailPanel.test.jsx` (16 cases across all five statuses) |
| TC58 | The frontend rule table drifting from the backend's | `test_the_frontend_mirror_matches_the_backend_rules` — reads `frontend/src/lib/transitions.js` and compares it with `app/transitions.py` |
| TC59 | BUG-18 returning — a non-recipient raising a release request | `test_an_analyst_or_admin_cannot_raise_a_release_request`, `test_the_ownership_rule_is_not_conditional_on_role` |
| TC60 | The permitted transitions still working after the guard was added | `test_every_permitted_transition_is_accepted` (6 cases) + smoke checks 12–14 |

---

## 7. PostgreSQL verification (12 August 2026)

PostgreSQL is the assessed target while the automated suite defaults to SQLite,
so the whole stack was run against a real PostgreSQL **16.6** server. This is the
evidence behind every "behaves the same on both engines" claim in this project.

**Cluster:** a throwaway PostgreSQL 16.6 instance on port 5433, created with
`initdb` from the official Windows binaries and used only for this verification.
It holds nothing but the synthetic seed data, is not registered as a service, and
can be deleted by stopping it and removing its directory:

```bash
pg_ctl -D <cluster-dir> -m fast stop
rm -rf <cluster-dir>
```

### What was verified

| # | Check | Result |
|---|---|---|
| 1 | `psql -v ON_ERROR_STOP=1 -f database/schema.sql` | applied cleanly, exit 0 |
| 2 | ORM compiled against the PostgreSQL dialect | 10 `CHECK` constraints emitted |
| 3 | Partial unique index present in `pg_indexes` | confirmed |
| 4 | `python -m app.seed` **into the psql-created tables** (no `--reset`) | 4 users, 8 emails |
| 5 | 6 invalid writes attempted directly in SQL | all 6 rejected |
| 6 | Full backend suite with `TEST_DATABASE_URL` | **175 passed** |
| 7 | `smoke_test.py` against the app on PostgreSQL | **22/22 passed** |
| 8 | `/system/database-status` | `"engine":"postgresql","using_fallback":false` |
| 9 | Screenshots 21–23 captured from the PostgreSQL-backed application | captured |

### The partial index, as PostgreSQL stores it

```sql
CREATE UNIQUE INDEX uq_request_one_pending_per_email_user
    ON public.staff_release_requests USING btree (email_id, requested_by)
    WHERE ((status)::text = 'pending'::text);
```

### Invalid writes, and the constraint that stopped each

```
INSERT ... role='superadmin'
  ERROR: violates check constraint "ck_users_role"
UPDATE email_records SET status='deleted'
  ERROR: violates check constraint "ck_email_status"
UPDATE email_records SET risk_score=1000
  ERROR: violates check constraint "ck_email_risk_score"
UPDATE email_records SET auth_spf='maybe'
  ERROR: violates check constraint "ck_email_spf"
INSERT a second pending request for the same (email, user)
  ERROR: duplicate key value violates unique constraint
         "uq_request_one_pending_per_email_user"
  DETAIL: Key (email_id, requested_by)=(2, 3) already exists.
INSERT a pending request that already names a reviewer
  ERROR: violates check constraint "ck_request_decision_complete"
```

The last of those — `ck_request_decision_complete`, which requires a decided
request to name its reviewer and a pending one not to — is also covered from the
application side by `test_a_decided_request_must_record_its_reviewer` and
`test_a_pending_request_must_not_record_a_reviewer`, which run against this same
PostgreSQL server as part of the 175.

### What running on PostgreSQL actually caught

Two things a SQLite-only run could not have found:

1. **BUG-16** — a concurrent duplicate release request returned `503 "please try
   again"` instead of `409`. The advice was impossible to act on, because the
   conflicting row is permanent until the request is decided.
2. **A defect inside that fix.** The first version identified the violation by
   the index name, which PostgreSQL includes and SQLite does not — SQLite names
   the columns instead. It passed on PostgreSQL and failed on SQLite. Running
   both engines is what exposed it.

Screenshots 21–23 in `evidence/screenshots/` were captured from the application
while it was connected to PostgreSQL; `capture_postgres_evidence.py` refuses to
run if the backend reports any other engine.

### Reproducing this

```bash
createdb phishguard_db && createdb phishguard_test
psql -d phishguard_db -v ON_ERROR_STOP=1 -f database/schema.sql

cd backend
export DATABASE_URL=postgresql+psycopg2://USER:PASS@localhost:5432/phishguard_db
export TEST_DATABASE_URL=postgresql+psycopg2://USER:PASS@localhost:5432/phishguard_test
python -m app.seed          # NOT --reset: that would drop the psql-created tables
python -m pytest            # 175 passed
uvicorn app.main:app --port 8000 &
python smoke_test.py        # ALL 22/22 CHECKS PASSED
```

The `backend-postgres` CI job performs the same sequence on every push.

---

## 8. Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request to `main`:

| Job | What it does |
|---|---|
| `backend` | Installs and runs the 175 tests + coverage on Python **3.11, 3.12 and 3.13** |
| `backend-postgres` | Starts a PostgreSQL 16 service, applies `database/schema.sql`, seeds and asserts 4 users + 8 emails, checks the constraints reject invalid SQL, then runs the whole 175-test suite against PostgreSQL |
| `secrets` | Runs `evidence/secret_scan.py` over every tracked file and fails the build on any unacknowledged credential, key or token |

The workflow declares **four jobs**. Because the backend job runs as a matrix across
Python 3.11, 3.12 and 3.13, one run performs **six job executions**, which is the
figure the report quotes. The local integrity probe rejects **6 invalid writes**; the
`backend-postgres` CI job checks **5 invalid-write categories**. These are different
checks and are not merged into a single number.
| `frontend` | `npm ci`, the 92 vitest tests, production `vite build` |

This matters for two reasons: the Python matrix is the regression guard for
BUG-01, and the PostgreSQL job means the *official* target database is exercised
by machine rather than only claimed in prose.

---

## 9. What is **not** tested

Stated honestly so no coverage claim is overstated.

1. **No browser end-to-end *assertion* suite.** Playwright drives a real browser
   through the whole workflow to capture the screenshots and the recording, so
   the browser → API → database path is genuinely exercised — but those scripts
   capture evidence rather than assert outcomes, so a regression would show up
   as a wrong-looking image, not a failing test. Component tests mock the API,
   and `smoke_test.py` drives the API without a browser.
2. **No load or performance testing.** No throughput or latency figure is
   claimed anywhere.
3. **No ML evaluation metrics.** There is no ML model in the MVP, so no
   precision/recall/F1 is reported. The rule engine's false-positive and
   false-negative behaviour is discussed qualitatively in `docs/SECURITY.md`;
   quantifying it would need a labelled corpus this project does not have.
4. **Timing-attack resistance is not asserted numerically** — `dummy_verify` is
   reviewed, not measured.
5. **The frontend production bundle is built but not smoke-tested in a browser
   by CI.** The build succeeding is verified; the served bundle is checked
   manually.
6. **No cross-browser or mobile-device matrix.** The layout uses responsive
   Tailwind breakpoints and wide tables scroll inside their own container, but
   this was verified by inspection, not by an automated device matrix.
7. **Parts of `main.py`'s startup logging and a branch of the session teardown**
   are not covered, which is why coverage is 90% and not higher. The two 0%
   modules are the unimplemented classifier placeholder and the seeding script.
8. **Concurrency is tested by reproducing the race window, not by real parallel
   requests.** `test_a_concurrent_duplicate_request_gets_409_not_503` neutralises
   the pre-check so the INSERT reaches the index exactly as a racing worker's
   would, which is deterministic and repeatable; it is not a load test with two
   simultaneous clients.
