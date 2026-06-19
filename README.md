# 🛡️ PhishGuard — Email Phishing Detection & Quarantine Management

> **MIT208 Practical MVP** — a full-stack email-security application that scores
> incoming email for phishing risk, lets security analysts quarantine / release /
> confirm threats, lets staff request the release of held email, and records an
> immutable audit trail of every action.

PhishGuard runs **entirely on localhost** for the demo. The first MVP uses a
transparent **rule-based risk-scoring engine**; a **DistilBERT** classifier is
documented as a planned future enhancement (`backend/app/ml_model.py`).

| Service | URL |
|---------|-----|
| Frontend (React + Vite) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| Interactive API docs (Swagger) | http://localhost:8000/docs |
| Database | PostgreSQL `phishguard_db` |

---

## ✨ Features

- **JWT + bcrypt authentication** with three roles: `analyst`, `staff`, `admin`.
- **Rule-based phishing risk scoring** (0–100) with fully explainable reasons —
  impersonation, urgency, credential-harvesting, lookalike links, raw-IP links,
  URL shorteners, risky attachments, and AI-generated-copy detection.
- **Email Inbox** with filter tabs — **All · High Risk · Uncertain · Safe** — and
  colour-coded risk badges (🔴 High Risk · 🟠 Uncertain · 🟢 Safe).
- **Email Detail panel** showing the risk score, an **AI-Generated** tag,
  simulated **SPF / DKIM / DMARC** results, and the list of threat indicators —
  with action buttons (**Quarantine · Release · Confirm Phishing · Submit
  Feedback · Copy ID**) directly under the subject.
- **Staff Portal** where staff review their own mailbox and **Request Email
  Release** for held messages.
- **Release Requests** queue where analysts approve / deny staff requests.
- **Audit Logs** — every login, quarantine, release, confirm, feedback and
  release-request decision is recorded with actor, entity, details and IP.

> ⚠️ **No real email data is used.** All sample messages are synthetic and all
> demo accounts use the non-routable `.local` domain.

---

## 🖼️ Screenshots

| Login | Dashboard |
|-------|-----------|
| ![Login](docs/screenshots/login.png) | ![Dashboard](docs/screenshots/dashboard.png) |

| Email Inbox + Detail | Staff Portal |
|----------------------|--------------|
| ![Email detail](docs/screenshots/email-detail.png) | ![Staff portal](docs/screenshots/staff-portal.png) |

| Audit Logs | Release Requests |
|------------|------------------|
| ![Audit logs](docs/screenshots/audit-logs.png) | ![Release requests](docs/screenshots/release-requests.png) |

---

## 🧱 Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, React Router, Axios, lucide-react |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, PyJWT, bcrypt |
| Database | **PostgreSQL** (official) · SQLite (zero-install fallback) |
| Auth | JWT access tokens + bcrypt password hashing |
| Scoring | Rule-based engine (`app/scoring.py`); DistilBERT planned (`app/ml_model.py`) |

---

## 📂 Project structure

```
Mit208/
├── backend/                # FastAPI application
│   ├── app/
│   │   ├── main.py         # app entrypoint + CORS
│   │   ├── config.py       # env-driven settings (DATABASE_URL, SECRET_KEY…)
│   │   ├── database.py     # SQLAlchemy engine/session (Postgres or SQLite)
│   │   ├── models.py       # 5 ORM tables
│   │   ├── schemas.py      # Pydantic request/response models
│   │   ├── security.py     # bcrypt + JWT
│   │   ├── deps.py         # auth dependency + role guards
│   │   ├── scoring.py      # rule-based phishing risk engine
│   │   ├── ml_model.py     # DistilBERT placeholder (future work)
│   │   ├── audit.py        # audit-log helper
│   │   ├── seed.py         # demo users + sample emails seeder
│   │   └── routers/        # auth, emails, requests, audit, dashboard
│   ├── requirements.txt
│   ├── .env.example
│   └── smoke_test.py       # end-to-end API test
├── frontend/               # React + Vite + Tailwind UI
│   └── src/
│       ├── pages/          # Login, Dashboard, Inbox, StaffPortal, ReleaseRequests, AuditLogs
│       ├── components/     # Sidebar, Layout, RiskBadge, EmailDetailPanel
│       ├── context/        # AuthContext
│       └── lib/            # risk-level mapping helpers
├── database/               # schema.sql, seed_data.sql, sample_emails.json
├── docs/screenshots/
└── README.md
```

---

## 🗄️ Database tables

| Table | Purpose |
|-------|---------|
| `users` | Accounts with role + bcrypt password hash |
| `email_records` | Ingested emails with risk score/level, reasons, SPF/DKIM/DMARC, AI flag, status |
| `analyst_reviews` | Every analyst action (quarantine / release / confirm_phishing / feedback) |
| `staff_release_requests` | Staff requests to release held email + analyst decision |
| `audit_logs` | Immutable trail of every action (actor, entity, details, IP, timestamp) |

---

## 🚀 Setup & run (localhost demo)

> **Prerequisites:** Python 3.11+ and Node.js 18+.
> PostgreSQL 14+ is **recommended** for the professor demo (see below); if it is
> not installed the backend automatically falls back to a local SQLite file so
> you can still run everything instantly.

### 1. Backend

```bash
cd backend
python -m venv .venv

# Activate the virtual environment:
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   macOS / Linux:         source .venv/bin/activate

pip install -r requirements.txt

# Configure the database (see "Database options" below)
cp .env.example .env        # then edit DATABASE_URL if needed

# Create demo users + sample emails
python -m app.seed --reset

# Start the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Open **http://localhost:5173** and sign in with a demo account below.

---

## 🐘 Database options

PhishGuard reads its connection string from **`DATABASE_URL`** in `backend/.env`.

### Option A — PostgreSQL (recommended for the professor demo)

```bash
# 1. Create the database
createdb phishguard_db
#    (or in psql:  CREATE DATABASE phishguard_db;)

# 2. In backend/.env set:
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/phishguard_db

# 3. Seed it
cd backend
python -m app.seed --reset
```

The backend auto-creates the tables on startup. You may also apply the reference
DDL and pure-SQL seed directly:

```bash
psql -d phishguard_db -f database/schema.sql
psql -d phishguard_db -f database/seed_data.sql
```

### Option B — SQLite fallback (instant, no install)

If `DATABASE_URL` is **not set at all**, PhishGuard defaults to a local SQLite
file (`backend/phishguard.db`) so the app runs immediately. This is intended
**only** for quick local testing — PostgreSQL is the official target. To force it
explicitly:

```bash
# backend/.env
DATABASE_URL=sqlite:///./phishguard.db
```

The SQLAlchemy models use no SQLite-specific features, so the exact same code
runs on PostgreSQL.

---

## 👤 Demo accounts

| Role | Email | Password | Can do |
|------|-------|----------|--------|
| **Analyst** | `analyst@phishguard.local` | `Analyst@123` | Inbox, quarantine/release/confirm/feedback, approve requests, audit logs |
| **Staff** | `staff@phishguard.local` | `Staff@123` | Own mailbox, request email release |
| **Staff** | `jane.staff@phishguard.local` | `Staff@123` | Own mailbox, request email release |
| **Admin** | `admin@phishguard.local` | `Admin@123` | Everything |

---

## 🎓 Professor demo script (≈ 5 minutes)

1. **Login** — open http://localhost:5173 and sign in as **Analyst**
   (`analyst@phishguard.local` / `Analyst@123`).
2. **Dashboard** — point out total emails, quarantined count, confirmed phishing,
   pending requests, and the risk breakdown.
3. **Email Inbox** — click the **High Risk** tab; note the red badges and risk
   scores. Open the *"Urgent: Your account has been suspended"* email (score 100).
4. **Email Detail** — show the **AI-Generated** tag, the failing **SPF/DKIM/DMARC**
   badges, and the **threat indicators** explaining the score.
5. **Take actions** — click **Quarantine**, then **Submit Feedback** (type a note),
   then **Confirm Phishing**. Each updates the database immediately.
6. **Audit Logs** — open **Audit Logs** and show that every action was recorded
   with actor, time and IP.
7. **Staff side** — sign out, sign in as **Staff** (`staff@phishguard.local` /
   `Staff@123`), open the **Staff Portal**, open a held email and click
   **Request Email Release** with a reason.
8. **Approve** — sign back in as the Analyst, open **Release Requests**, and
   **Approve** the staff request — the email is released and the decision is
   audited.
9. **API docs** — open http://localhost:8000/docs to show the live REST API and
   the *Authorize* button (OAuth2 password flow).

---

## 🧪 Automated end-to-end test

With the backend running, you can replay the whole workflow against the API:

```bash
cd backend
python smoke_test.py
# → ALL 11/11 CHECKS PASSED
```

It exercises login, dashboard stats, quarantine, release, confirm-phishing,
feedback, staff release request, analyst approval, audit logging, and
role-based access control.

---

## 🔭 Future work — DistilBERT

The MVP ships with a transparent rule engine. The next iteration will fine-tune
**`distilbert-base-uncased`** on a labelled phishing corpus and blend its
probability with the rule score. The integration point is stubbed in
`backend/app/ml_model.py` so it can be added without changing the API contract.

---

## 📜 Notes

- This is an educational MVP for the MIT208 unit; the `SECRET_KEY` in
  `.env.example` is a development placeholder — change it for any real deployment.
- SPF/DKIM/DMARC results are **simulated** from the synthetic sample data (there
  are no real SMTP headers in the demo dataset).
