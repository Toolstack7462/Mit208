# PhishGuard

**Phishing email detection, review and quarantine management — MIT208 Project 2**

[![CI](https://github.com/Toolstack7462/Mit208/actions/workflows/ci.yml/badge.svg)](https://github.com/Toolstack7462/Mit208/actions/workflows/ci.yml)

## Project Overview

This repository contains the practical implementation of PhishGuard, a phishing
email review and quarantine system developed for MIT208. The application includes
a React frontend, FastAPI backend, database models, sample email data, analyst
actions, staff release requests, and audit logging.

The system runs entirely on localhost. All sample messages are synthetic and no
real email data is used.

| Service | URL |
|---------|-----|
| Frontend (React + Vite) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| Interactive API documentation | http://localhost:8000/docs |
| Database | PostgreSQL `phishguard_db` (SQLite fallback available) |

**Assessed version:** [`v1.3-final`](https://github.com/Toolstack7462/Mit208/releases/tag/v1.3-final).
Earlier `*-final` tags mark intermediate states and were left where they point
rather than moved.

**Verified status (12 August 2026):** 170 backend tests pass on **both SQLite and
PostgreSQL 16.6**, 92 frontend tests pass, and 22 live end-to-end API checks pass
against a running server; backend statement coverage is 90% (847/943). Twenty-four
screenshots and a 4-minute walkthrough were captured from the running application.
See [`docs/TESTING.md`](docs/TESTING.md) for the commands and captured output.

---

## Problem Addressed

Phishing remains the most common initial access route into an organisation, and
the two usual responses both fail in practice. A filter that silently deletes
suspicious mail destroys legitimate messages with no recourse, and a filter that
simply tags mail leaves an untrained recipient to make the security decision.
Neither leaves any record of who decided what.

PhishGuard addresses the gap between those two extremes:

- **Suspicious mail is held, not deleted.** Messages scoring high or critical are
  quarantined automatically, so nothing dangerous is delivered and nothing
  legitimate is lost.
- **Every score is explainable.** The rule engine returns a plain-language reason
  for each point it adds, so an analyst can judge the finding instead of
  trusting an opaque number.
- **The recipient has a route back.** Staff can see that a message is held and
  request its release with a written justification, rather than emailing IT and
  waiting.
- **The decision is a security decision, made by a security person.** Only an
  analyst or admin can release mail.
- **Everything is recorded.** Every login, classification, action and decision is
  written to an audit log with actor, entity, detail and IP address. The log is
  append-only at the application level: no route updates or deletes a row. It is
  not immutable storage — a database administrator with direct SQL access could
  still change the table. See [`docs/SECURITY.md`](docs/SECURITY.md).

**Target users:** security analysts (triage and decide), general staff (see their
own held mail and request release), and administrators (full oversight).

---

## Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Component diagram, request lifecycle, end-to-end workflow, design decisions |
| [`docs/ERD.md`](docs/ERD.md) | Entity-relationship diagram, relationships, indexes, integrity rules |
| [`docs/API.md`](docs/API.md) | All 19 endpoints with request/response examples and status codes |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy, documented test cases, verified results, coverage |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Security controls with the test proving each, plus known limitations |
| [`docs/BUG_LOG.md`](docs/BUG_LOG.md) | 18 defects found, investigated and fixed, each with a regression test |
| [`docs/SUBMISSION_CHECKLIST.md`](docs/SUBMISSION_CHECKLIST.md) | What is done, what is still manual, and how to verify each item |
| [`docs/DEMO.md`](docs/DEMO.md) | Exact startup and database-reset commands, demo accounts, the route through the app, and the offline fallback |
| [`evidence/README.md`](evidence/README.md) | How the screenshots and walkthrough recording were produced |

---

## Features

- Role-based authentication (analyst, staff, admin) using JWT access tokens and
  bcrypt password hashing.
- Rule-based phishing risk scoring (0–100) with fully explainable indicators:
  sender impersonation, urgency language, credential harvesting, look-alike
  links, raw-IP links, URL shorteners, risky attachments, and AI-generated-copy
  detection.
- Email inbox with filter tabs — All, High Risk, Uncertain, Safe — and
  colour-coded risk badges (High Risk red, Uncertain amber, Safe green).
- Email detail view showing the risk score, an AI-generated content tag,
  simulated SPF/DKIM/DMARC authentication results, and the list of threat
  indicators.
- Analyst actions: quarantine, release, confirm phishing, and submit feedback.
- Staff portal for requesting release of held emails.
- Release-request queue with analyst/admin approval and denial.
- Audit log recording every action with actor, entity, details and IP address.
- Dashboard with summary statistics, a weekly threat-distribution chart, and a
  threat-category distribution chart.
- Input validation on every write endpoint, with limits matched to the database
  column widths so behaviour is identical on PostgreSQL and SQLite.
- Consistent API error envelope with a traceable `request_id`, and distinct
  loading / error / empty states in the UI with a retry action.
- Brute-force protection on login (per-IP failed-attempt limit), enforced JWT
  signing-key strength, and typed tokens carrying `iat`/`jti`/`typ`.
- Database-level integrity: `CHECK` constraints on every enumerated column, a
  bounded `risk_score`, and a partial unique index making "one open release
  request per user per email" atomic rather than merely checked in the API.
- Defensive parsing of stored data, so a corrupt `score_reasons` value no longer
  makes the whole record unreadable (BUG-09), and per-request rollback so a failed
  action writes nothing.

### Not implemented (stated deliberately)

- **The DistilBERT classifier is not built.** `backend/app/ml_model.py` documents
  the intended integration point and raises `NotImplementedError`; it is not
  called by any running code path. Every risk score in the working system comes
  from the rule engine in `backend/app/scoring.py`.
- **SPF/DKIM/DMARC results are simulated**, derived from the rule engine's own
  spoofing signals. The synthetic sample data contains no real SMTP headers, so
  no real authentication check is performed.
- **No live mail ingestion.** Emails enter through the seed script or the
  `POST /api/emails` endpoint, not from a mail server.

None of these gaps affects the core MVP workflow.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, React Router, Axios |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, PyJWT, bcrypt |
| Database | PostgreSQL (primary), SQLite (zero-install fallback) |
| Authentication | JWT access tokens with bcrypt password hashing |
| Risk scoring | Rule-based engine (`app/scoring.py`) |

---

## Project Structure

```
Mit208/
├── backend/                # FastAPI application
│   ├── app/
│   │   ├── main.py         # Application entrypoint and CORS configuration
│   │   ├── config.py       # Environment-driven settings
│   │   ├── database.py     # SQLAlchemy engine and session
│   │   ├── models.py       # ORM models for the five tables
│   │   ├── schemas.py      # Pydantic request/response models
│   │   ├── security.py     # bcrypt hashing and JWT helpers
│   │   ├── deps.py         # Authentication dependency and role guards
│   │   ├── scoring.py      # Rule-based phishing risk engine
│   │   ├── ml_model.py     # Placeholder for the future DistilBERT classifier
│   │   ├── audit.py        # Audit-log helper
│   │   ├── seed.py         # Demo users and sample-email seeder
│   │   ├── ratelimit.py    # Per-IP failed-login limiter
│   │   └── routers/        # auth, emails, requests, audit, dashboard
│   ├── tests/              # 170 pytest tests (9 files), run on SQLite + PostgreSQL
│   ├── smoke_test.py       # 22 live end-to-end API checks
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/               # React + Vite + Tailwind UI
│   └── src/
│       ├── pages/          # Login, Dashboard, Inbox, StaffPortal, ReleaseRequests, AuditLogs
│       ├── components/     # Sidebar, Layout, RiskBadge, EmailDetailPanel, charts, StateBlock
│       ├── context/        # Authentication context
│       ├── lib/            # risk.js, errors.js, transitions.js (email state machine)
│       ├── test/           # Vitest setup
│       └── **/*.test.jsx   # 92 vitest tests (11 files)
├── database/               # schema.sql, seed_data.sql, sample_emails.json
├── docs/                   # ARCHITECTURE, ERD, API, TESTING, SECURITY, BUG_LOG,
│                           #   SUBMISSION_CHECKLIST, DEMO
├── evidence/               # capture/recording scripts, 24 screenshots, MP4 walkthrough
├── .github/workflows/      # ci.yml — backend matrix, PostgreSQL job, secret scan,
│                           #   frontend build
└── README.md
```

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `users` | Accounts with role and bcrypt password hash |
| `email_records` | Ingested emails with risk score/level, reasons, SPF/DKIM/DMARC, AI flag and status |
| `analyst_reviews` | Analyst actions: quarantine, release, confirm_phishing, feedback |
| `staff_release_requests` | Staff requests to release held email and the analyst decision |
| `audit_logs` | Record of every action (actor, entity, details, IP, timestamp) |

---

## Local Setup

**Prerequisites**

| Requirement | Version | Notes |
|---|---|---|
| Python | **3.11 – 3.14** | Tested on 3.14.3 locally; CI covers 3.11, 3.12 and 3.13 |
| Node.js | **18+** | Tested on 24.14.1; CI uses 20 |
| PostgreSQL | 14+ | Recommended. If absent, the backend falls back to a local SQLite file and still runs |

Dependencies are pinned with the compatible-release operator (`~=`) rather than
exact `==` pins. This is deliberate: the earlier exact pins would not install on
Python 3.13+, because `pydantic-core` and `psycopg2` publish binary wheels only for
the interpreters that existed when that patch was released. `~=` keeps the same
minor version but allows a newer patch that does ship a matching wheel. See
[`docs/BUG_LOG.md`](docs/BUG_LOG.md) BUG-01. The CI matrix installs the pinned
requirements on Python 3.11, 3.12 and 3.13 on every push, so a regression of that
kind would show up there rather than on a marker's machine.

```bash
git clone https://github.com/Toolstack7462/Mit208.git
cd Mit208
```

---

## Database Setup

PhishGuard reads its configuration from `backend/.env`. A template is provided as
`backend/.env.example` — copy it to `backend/.env` and fill in real values. The
`.env` file is excluded from version control; only `.env.example` is committed,
and it contains **no working credentials or keys**.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./phishguard.db` | Connection string. PostgreSQL is the official target |
| `ENVIRONMENT` | `development` | `production` refuses a weak `SECRET_KEY` and hides internal error detail |
| `SECRET_KEY` | *(none usable)* | **Required.** JWT signing key, ≥ 32 characters |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Token lifetime |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allow-list entry |
| `LOGIN_MAX_ATTEMPTS` | `10` | Failed logins allowed per IP per window |
| `LOGIN_WINDOW_SECONDS` | `300` | Rolling window for the above |

### Generating a signing key

`SECRET_KEY` has **no usable default**. A predictable signing key would let anyone
forge an admin token, so the application will not quietly accept one:

- With `ENVIRONMENT=production`, a missing, short or placeholder key makes the
  app **refuse to start**.
- In development it starts but signs tokens with a random per-process key and logs
  a warning — so sessions do not survive a restart until you configure one.

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the result into `SECRET_KEY` in `backend/.env`.

PostgreSQL is the official target database. SQLite is supported only as a
zero-install fallback for quick local testing.

### PostgreSQL (recommended)

```bash
# 1. Create the database
createdb phishguard_db
#    (or in psql:  CREATE DATABASE phishguard_db;)

# 2. In backend/.env set (substitute your own role and password):
DATABASE_URL=postgresql+psycopg2://YOUR_DB_USER:YOUR_DB_PASSWORD@localhost:5432/phishguard_db
```

`backend/.env` is listed in `.gitignore` and is never committed; only
`backend/.env.example` is tracked. `evidence/secret_scan.py` checks that.

The backend creates the tables automatically on startup. The reference DDL and a
pure-SQL seed can also be applied directly:

```bash
psql -d phishguard_db -f database/schema.sql
psql -d phishguard_db -f database/seed_data.sql
```

### SQLite fallback

If `DATABASE_URL` is not set, the application defaults to a local SQLite file
(`backend/phishguard.db`) and runs without any database installation. To set it
explicitly:

```bash
# backend/.env
DATABASE_URL=sqlite:///./phishguard.db
```

The SQLAlchemy models use no SQLite-specific features, so the same code runs on
PostgreSQL.

---

## Running the Backend

```bash
cd backend
python -m venv .venv

# Activate the virtual environment:
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   macOS / Linux:         source .venv/bin/activate

pip install -r requirements.txt

# Copy the environment template, then set DATABASE_URL and SECRET_KEY
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into SECRET_KEY

# Create demo users and sample emails
python -m app.seed --reset

# Start the API (http://localhost:8000, documentation at /docs)
uvicorn app.main:app --reload --port 8000
```

---

## Running the Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Open http://localhost:5173 and sign in with one of the accounts below.

---

## Demo Login Credentials

| Role | Email | Password |
|------|-------|----------|
| Analyst | `analyst@phishguard.local` | `Analyst@123` |
| Staff | `staff@phishguard.local` | `Staff@123` |
| Staff | `jane.staff@phishguard.local` | `Staff@123` |
| Admin | `admin@phishguard.local` | `Admin@123` |

All email addresses use the non-routable `.local` domain. These demo passwords
are for local testing only and are stored in the database as bcrypt hashes.

---

## Application Workflow

- Incoming emails are scored by the rule-based engine on ingestion and assigned a
  risk level. High and critical emails are placed in quarantine automatically.
- Analysts review scored emails in the inbox, inspect the threat indicators and
  authentication results, and take an action: quarantine, release, confirm
  phishing, or submit feedback.
- Staff view their own mailbox and submit a release request for any held email
  they believe is legitimate.
- Analysts or admins review release requests and approve or deny them; an approval
  releases the underlying email.
- Every action is written to the audit log with the actor, affected entity,
  details and originating IP address.

---

## Local Demo Workflow

1. Start the backend server.
2. Start the frontend server.
3. Sign in using the demo analyst account.
4. Open the dashboard.
5. Review flagged emails.
6. Open a high-risk email.
7. Quarantine or release the email.
8. Confirm the audit log entry.
9. Submit a staff release request.
10. Review the request from the analyst/admin view.

---

## API Documentation

The backend exposes an interactive OpenAPI (Swagger) interface at
http://localhost:8000/docs. It documents every endpoint and includes an
authorisation control that accepts a token from the OAuth2 password flow.

Primary endpoint groups:

| Group | Description |
|-------|-------------|
| `/api/auth` | Login and current-user details |
| `/api/emails` | List/view emails and analyst actions |
| `/api/release-requests` | Create and decide staff release requests |
| `/api/audit-logs` | Read the audit trail |
| `/api/dashboard` | Aggregate dashboard statistics |
| `/health` | Application status and live database-connectivity check |
| `/system/database-status` | Reports the active engine (PostgreSQL or SQLite fallback) |

Example status responses:

```bash
curl http://localhost:8000/health
# {"status":"ok","app":"PhishGuard API","version":"1.0.0","database_connected":true}

curl http://localhost:8000/system/database-status
# {"engine":"postgresql","type":"PostgreSQL","using_fallback":false,...}
```

A full written reference — all 19 endpoints with request/response examples, status
codes and the error format — is in [`docs/API.md`](docs/API.md).

An end-to-end check of the workflow is available in `backend/smoke_test.py` and
can be run while the backend is active (22 checks).

---

## Testing

Three complementary layers. Full detail, 66 documented test cases and captured
output are in [`docs/TESTING.md`](docs/TESTING.md).

| Layer | Location | Coverage |
|---|---|---|
| Backend unit + API (pytest) | `backend/tests/` | **170 tests**, run on SQLite **and** PostgreSQL — rule engine, JWT auth, RBAC, email actions, the workflow state machine, release workflow, validation, security controls, database integrity, concurrency, dashboard, audit |
| Frontend unit + component (vitest) | `frontend/src/**/*.test.{js,jsx}` | **92 tests** — error mapping, risk helpers, route/role guards, login flow, error & empty states, release-request validation, action-button availability, notification tone |
| Live end-to-end | `backend/smoke_test.py` | **22 checks** against a real running server and database |

**Verified results (11 August 2026):** 170 passed on SQLite · 170 passed on
PostgreSQL 16.6 · 92 frontend passed · 22/22 live checks passed against the
PostgreSQL-backed server. Backend statement coverage **90%** (847/943).

The pytest suite runs against an **isolated in-memory SQLite database** (it never
touches `phishguard.db`), so it is safe to run at any time and requires no server:

```bash
# Backend
cd backend
pip install -r requirements-dev.txt
python -m pytest                                       # 170 passed (SQLite)

# The same suite against PostgreSQL, the assessed target. Create the database,
# point TEST_DATABASE_URL at it, then run the suite again:
#   createdb phishguard_test
#   PowerShell:      $env:TEST_DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@localhost:5432/phishguard_test"
#   macOS / Linux:   export TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/phishguard_test
python -m pytest                                       # 170 passed (PostgreSQL)
python -m pytest --cov=app --cov-report=term-missing   # with coverage

# Frontend
cd ../frontend
npm install
npm test                                               # 92 passed

# Live end-to-end (needs the server running and the database seeded)
cd ../backend
python -m app.seed --reset
uvicorn app.main:app --port 8000     # terminal 1
python smoke_test.py                 # terminal 2 -> ALL 22/22 CHECKS PASSED
```

### Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push and pull
request to `main`:

| Job | What it verifies |
|---|---|
| `backend` | Installs and runs the suite + coverage on Python 3.11, 3.12 and 3.13 |
| `backend-postgres` | Applies `database/schema.sql` to a real PostgreSQL 16 service with `ON_ERROR_STOP`, seeds into it, asserts the database rejects five kinds of invalid write, runs the **whole test suite** against PostgreSQL, and checks the ORM emits the same constraints |
| `frontend` | `npm ci`, the 92-test vitest suite, and a production `vite build` |

---

## Screenshots

All images are captures of the running application, taken with Playwright and
Chromium at 3200 x 2000 by [`evidence/capture_screenshots.py`](evidence/capture_screenshots.py).
The full set of 24, with a description of each, is in
[`evidence/screenshots/INDEX.md`](evidence/screenshots/INDEX.md). I re-run the
script after an interface change so the screenshots stay in step with the code.

| Login | Analyst dashboard |
|-------|-----------|
| ![Login](evidence/screenshots/01-login.png) | ![Dashboard](evidence/screenshots/03-analyst-dashboard.png) |

| Risk-sorted inbox | Explainable score |
|-------------|--------------|
| ![Email inbox](evidence/screenshots/04-analyst-inbox.png) | ![Email detail](evidence/screenshots/06-email-detail-explainable-score.png) |

| Staff portal | Release-request queue |
|--------------|------------------|
| ![Staff portal](evidence/screenshots/09-staff-portal.png) | ![Release requests](evidence/screenshots/08-release-requests-analyst.png) |

| Audit trail | API documentation |
|------------|-------------------|
| ![Audit logs](evidence/screenshots/07-audit-log.png) | ![FastAPI docs](evidence/screenshots/17-openapi-docs.png) |

Validation and failure behaviour is captured too — a refused duplicate request,
a refused short justification, and the dashboard when the API cannot be reached:

| Duplicate refused | Backend unreachable |
|---|---|
| ![Duplicate refused](evidence/screenshots/12-duplicate-request-blocked.png) | ![API unreachable](evidence/screenshots/16-error-state-api-unreachable.png) |

So is the workflow state machine. The interface offers only the transitions the
API accepts, so an invalid action is not offered in the first place; if one is sent
directly to the API anyway, it is refused with a 409:

| Release unavailable on delivered email | Request unavailable to the recipient |
|---|---|
| ![Invalid transition blocked](evidence/screenshots/18-invalid-transition-blocked.png) | ![Request not applicable](evidence/screenshots/19-release-request-not-applicable.png) |

---

## Walkthrough recording

[`evidence/video/PhishGuard_Walkthrough.mp4`](evidence/video/PhishGuard_Walkthrough.mp4)
— 4:00, 1280x720, H.264, **silent**. A capture of the real application produced by
[`evidence/record_walkthrough.py`](evidence/record_walkthrough.py), paced to the
five segments the assessment brief asks for. The on-screen timeline is in
`evidence/video/TIMING.md`.

The audio track is intentionally empty: the narration script and shot list are in
[`evidence/NARRATION_SCRIPT.md`](evidence/NARRATION_SCRIPT.md) so the narration is
recorded in the author's own voice rather than synthesised.

---

## Limitations

Stated honestly. None of these is claimed as solved, and none prevents the core
MVP workflow from working end to end. The security-specific list with reasoning
is in [`docs/SECURITY.md`](docs/SECURITY.md#8-known-limitations).

**Scope**

1. **No ML classifier.** `backend/app/ml_model.py` is a documented integration
   point that raises `NotImplementedError`. All scoring is rule-based.
2. **SPF/DKIM/DMARC are simulated** from the rule engine's own signals; the
   synthetic dataset has no real SMTP headers.
3. **No live mail ingestion.** Emails arrive via the seed script or
   `POST /api/emails`, not from a mail server.
4. **No user self-service.** No registration, password reset or profile editing;
   accounts come from the seed script.
5. **No email notifications.** Staff see request status in the portal only.

**Security**

6. **JWT is stored in `localStorage`**, so it is readable by any script that
   achieves XSS. An `HttpOnly` cookie would be safer but needs CSRF protection
   and a same-site deployment.
7. **No HTTPS** in the local demo; tokens are not encrypted in transit.
8. **No token revocation.** Logout clears the client copy only; a token stays
   valid until it expires. Deactivating an account does block access
   immediately, because `is_active` is re-checked on every request.
9. **Rate-limit state is per-process.** With multiple Uvicorn workers each keeps
   its own budget; a shared store would be needed for a real deployment.
10. **Rate limiting is per IP, not per account**, so a distributed attacker is
    not slowed.

**Data and testing**

11. **Enumerated columns use `CHECK` constraints, not PostgreSQL `ENUM` types.**
    That is deliberate — `CHECK` behaves identically on SQLite, so the automated
    suite exercises the same rules the assessed database applies — but native
    enumerated types would be stricter still.
12. **No browser end-to-end test.** Component tests mock the API and
    `smoke_test.py` drives the API without a browser, so the browser → API →
    database path is verified by the captured screenshots and recording rather
    than by an automated browser suite.
13. **No accuracy metric for the rule engine.** It will produce false positives
    and false negatives; quantifying that needs a labelled corpus this project
    does not have. Human review is the compensating control.
14. **No dependency vulnerability scanning in CI.**
15. **The login page pre-fills the demo analyst credentials.** This is a
    deliberate convenience for the demo and the live showcase, and would be
    wrong in a real product.

---

## Future Improvements

- Integrate a fine-tuned DistilBERT classifier and blend its probability with the
  rule-based score. The integration point is defined in `backend/app/ml_model.py`.
- Connect to a live mail source for real-time ingestion.
- Add a browser end-to-end suite (Playwright) to cover the full UI path.
- Move `status`, `role` and `risk_level` to database enumerated types.
- Move rate-limit state to Redis so it holds across workers.
- Add `pip-audit` and `npm audit` steps to CI.
- Add analytics over a longer time range and exportable reports.

---

## AI-Use Note

Generative AI (Claude) supported this project in three ways: reviewing the
prototype against the assessment criteria, helping debug problems such as why the
pinned dependencies would not install on newer Python releases, and suggesting
extra test cases, mostly negative and boundary ones.

I reviewed and tested every suggestion before adopting it, and I remain
responsible for the code, the security decisions and the results reported here.
Each defect in [`docs/BUG_LOG.md`](docs/BUG_LOG.md) was reproduced with a probe
test first, then fixed, then locked in with a named regression test. The figures in
that file and in [`docs/TESTING.md`](docs/TESTING.md) are recorded command output
from this repository, not generated text. Suggestions I decided against are listed
in the "investigated and deliberately not changed" table at the end of the bug log.

The full declaration required by the assessment is in the final report.

---

## Author

**MIT208 Project 2 (Implementation) — Assessment 3**
Melbourne Institute of Higher Education

Repository: <https://github.com/Toolstack7462/Mit208>

> Student name and ID are recorded on the report title page and in the Moodle
> submission rather than in this public repository.
