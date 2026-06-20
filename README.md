# PhishGuard

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
| Database | PostgreSQL `phishguard_db` |

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
│   │   └── routers/        # auth, emails, requests, audit, dashboard
│   ├── requirements.txt
│   └── .env.example
├── frontend/               # React + Vite + Tailwind UI
│   └── src/
│       ├── pages/          # Login, Dashboard, Inbox, StaffPortal, ReleaseRequests, AuditLogs
│       ├── components/     # Sidebar, Layout, RiskBadge, EmailDetailPanel, charts
│       ├── context/        # Authentication context
│       └── lib/            # Risk-level mapping helpers
├── database/               # schema.sql, seed_data.sql, sample_emails.json
├── screenshots/            # UI and API documentation screenshots
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

**Prerequisites:** Python 3.11+ and Node.js 18+. PostgreSQL 14+ is recommended;
if it is not installed, the backend automatically falls back to a local SQLite
file so the application still runs.

```bash
git clone https://github.com/Toolstack7462/Mit208.git
cd Mit208
```

---

## Database Setup

PhishGuard reads its connection string from `DATABASE_URL` in `backend/.env`.
A template is provided as `backend/.env.example` — copy it to `backend/.env`
and adjust as needed. The `.env` file is excluded from version control; only
`.env.example` is committed.

PostgreSQL is the official target database. SQLite is supported only as a
zero-install fallback for quick local testing.

### PostgreSQL (recommended)

```bash
# 1. Create the database
createdb phishguard_db
#    (or in psql:  CREATE DATABASE phishguard_db;)

# 2. In backend/.env set:
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/phishguard_db
```

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

# Copy the environment template and adjust DATABASE_URL if required
cp .env.example .env

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

An end-to-end check of the workflow is available in `backend/smoke_test.py` and
can be run while the backend is active.

---

## Screenshots

| Login | Dashboard |
|-------|-----------|
| ![Login](screenshots/login.png) | ![Dashboard](screenshots/dashboard.png) |

| Email Inbox | Email Detail |
|-------------|--------------|
| ![Email inbox](screenshots/email-inbox.png) | ![Email detail](screenshots/email-detail.png) |

| Staff Portal | Release Requests |
|--------------|------------------|
| ![Staff portal](screenshots/staff-portal.png) | ![Release requests](screenshots/release-requests.png) |

| Audit Logs | API Documentation |
|------------|-------------------|
| ![Audit logs](screenshots/audit-logs.png) | ![FastAPI docs](screenshots/fastapi-docs.png) |

---

## Future Improvements

- Integrate a fine-tuned DistilBERT classifier and blend its probability with the
  rule-based score. The integration point is defined in `backend/app/ml_model.py`.
- Connect to a live mail source for real-time ingestion.
- Add analytics over a longer time range and exportable reports.
- Expand automated test coverage across the API and frontend.

---

The `SECRET_KEY` value in `.env.example` is a development placeholder and should
be replaced before any non-local deployment. SPF/DKIM/DMARC results are simulated
from the synthetic sample data, as the demo dataset contains no real SMTP headers.
