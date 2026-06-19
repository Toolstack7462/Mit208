# Database

PostgreSQL database: **`phishguard_db`**

## Files
| File | Purpose |
|------|---------|
| `schema.sql` | Reference DDL for all 5 tables (`users`, `email_records`, `analyst_reviews`, `staff_release_requests`, `audit_logs`). |
| `sample_emails.json` | The synthetic sample emails (phishing + safe) used by the seeder, for transparency. |

## How seeding works
Tables are created automatically by the backend on startup, and **demo data is
seeded with Python** (`backend/app/seed.py`) so that bcrypt password hashes are
generated correctly — you cannot store a usable login password in plain SQL.

```bash
# from the backend/ folder, with the venv active
python -m app.seed --reset    # drops, recreates and re-seeds everything
```

`schema.sql` is optional and provided for reference / for inspecting the schema
without running the app:

```bash
createdb phishguard_db
psql -d phishguard_db -f database/schema.sql
```

## Demo accounts (created by the seeder)
| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@phishguard.local` | `Admin@123` |
| Analyst | `analyst@phishguard.local` | `Analyst@123` |
| Staff | `staff@phishguard.local` | `Staff@123` |
| Staff | `jane.staff@phishguard.local` | `Staff@123` |

> All email addresses use the non-routable `.local` domain and **no real email
> data is used** — every sample message is synthetic.
