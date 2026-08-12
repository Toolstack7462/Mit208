# Live showcase — exact steps

Everything needed to run PhishGuard in front of the lecturer on **19 August 2026**,
including what to do if the machine, the network or PostgreSQL will not cooperate.

Nothing here needs the internet once the dependencies are installed.

---

## 0. The five minutes before the session

```bash
git switch --detach v1.5-final     # the assessed version
git status                         # must print "nothing to commit, working tree clean"
```

Then run the two commands in section 2, confirm the browser loads, and **leave both
terminals running**. Starting from cold in front of an audience is what goes wrong.

Have open in separate browser tabs:

| Tab | Address | Why |
|---|---|---|
| 1 | http://localhost:5173 | the application |
| 2 | http://127.0.0.1:8000/docs | the generated API surface |
| 3 | http://127.0.0.1:8000/system/database-status | proof of which engine is live |
| 4 | https://github.com/Toolstack7462/Mit208 | the repository |
| 5 | https://github.com/Toolstack7462/Mit208/actions | the passing CI run |
| 6 | https://github.com/Toolstack7462/Mit208/releases/tag/v1.5-final | the assessed version |

---

## 1. One-time setup

```bash
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # PowerShell
#   source .venv/bin/activate         # macOS / Linux
pip install -r requirements-dev.txt

# Frontend
cd ../frontend
npm ci                               # reproducible install from package-lock.json
```

Python 3.11 – 3.14 and Node 20+ are supported. The pins use the compatible-release
operator, which allows a newer patch release of each dependency; CI installs them on
Python 3.11, 3.12 and 3.13 on every push, so an install failure of the kind in
BUG-01 would surface there first. See BUG-01 in `docs/BUG_LOG.md`.

---

## 2. Starting the application

Two terminals, in this order.

**Terminal 1 — backend**

```bash
cd backend
python -m app.seed --reset          # drop, recreate and seed: 4 users, 8 emails
uvicorn app.main:app --port 8000
```

**Terminal 2 — frontend**

```bash
cd frontend
npm run dev                          # serves http://localhost:5173
```

Wait for `Ready` in terminal 2 and for
http://127.0.0.1:8000/health to return `"database_connected": true`.

---

## 3. Resetting the database mid-demo

The demo performs real actions — it quarantines mail, raises a release request and
approves it. To run the workflow a second time, reset and restart:

```bash
# In terminal 1: Ctrl+C, then
python -m app.seed --reset
uvicorn app.main:app --port 8000
```

`--reset` drops every table and rebuilds it from the ORM. **Do not** use `--reset`
against a database whose tables were created by `database/schema.sql` — it would
replace the committed reference schema with the ORM's version. Seed without
`--reset` in that case.

Reset takes about two seconds. Practise it once so it is not the first time.

---

## 4. Demo accounts

Synthetic accounts on the reserved `.local` domain. They exist only in the local
throwaway database and unlock nothing else.

| Role | Email | Password | What it can do |
|---|---|---|---|
| Analyst | `analyst@phishguard.local` | `Analyst@123` | Review every email, act on it, read the audit log, decide release requests |
| Staff | `staff@phishguard.local` | `Staff@123` | See only mail addressed to this user; raise one release request per email |
| Staff | `jane.staff@phishguard.local` | `Staff@123` | A second mailbox, for showing that staff data really is scoped |
| Admin | `admin@phishguard.local` | `Admin@123` | Everything the analyst can do |

They are also listed on the sign-in screen, so no password needs to be typed from
memory.

---

## 5. The five-minute route through the application

1. **Sign in wrong first.** Any password → the banner is the API's own 401, not a
   browser-side check.
2. **Analyst dashboard.** Counts by status, the weekly distribution, the risk mix.
3. **Inbox.** Sorted by risk. Filter to **High Risk**.
4. **Open the score-100 message.** Six named indicators — the impersonated display
   name against the `paypa1` domain, the raw-IP link, the mismatched link text.
   This is the point of the project: the score is explainable.
5. **Note the disabled buttons.** On this confirmed-phishing message, Quarantine
   and Confirm Phishing are greyed out and Release is not. The interface offers
   only the transitions `app/transitions.py` allows.
6. **Sign in as staff.** Only that user's mail is listed — the filter is in the
   database query, not the interface.
7. **Request release with a 3-character reason** → refused. Then a real one →
   accepted. Click again → refused, one open request per email.
8. **Back as the analyst, approve it.** Request, email status, review row and audit
   row all move in one transaction.
9. **Audit log.** Actor, action, entity, detail, IP address.
10. **As staff, navigate to `/audit`** → redirected, and the API returns 403 on its
    own. Say plainly that the route guard is convenience, not the control.

---

## 6. Questions to expect, and where the answer lives

| Question | Answer | File |
|---|---|---|
| "Show me where the role is checked." | `require_roles(...)` re-reads the user from the database every request; the token's role claim is never trusted | `app/deps.py` |
| "What stops an invalid action?" | One table of action → valid source statuses, imported by both routes that can move an email | `app/transitions.py` |
| "Is that enforced anywhere else?" | CHECK constraints on every enumerated column and a partial unique index for pending requests | `database/schema.sql` |
| "How is the score produced?" | A pure function: bounded points per indicator, stored with its reasons | `app/scoring.py` |
| "Is the ML part real?" | No. It is a documented placeholder that no running code path calls | `app/ml_model.py` |
| "How do you know it works on PostgreSQL?" | The whole suite runs on it locally and in CI, plus the schema and constraint checks | `docs/TESTING.md` §7 |
| "Show me a bug you fixed." | BUG-17 and BUG-18, each with the reasoning and a named regression test | `docs/BUG_LOG.md` |

---

## 7. If something fails

**Port already in use.** Run on another port and tell the frontend where to look:

```bash
uvicorn app.main:app --port 8001
# frontend/.env  ->  VITE_API_URL=http://127.0.0.1:8001
```

**PostgreSQL will not start.** Do not fight it. The application falls back to
SQLite automatically when `DATABASE_URL` is unset, and every feature behaves the
same — the test suite proves it on both engines. Say so, show
`/system/database-status` reporting `"using_fallback": true`, and continue. The
PostgreSQL evidence is already captured in screenshots 21–23 and in the CI run.

**`npm run dev` fails.** Serve the production build that is already verified:

```bash
cd frontend
npm run build
npm run preview -- --port 5173
```

**Nothing runs at all.** The offline fallback, in order of preference:

1. `evidence/video/PhishGuard_Walkthrough.mp4` — four minutes of the real
   application doing the whole workflow.
2. `evidence/screenshots/` — 25 labelled captures with a generated index.
3. The report's Appendix E — selected screens at full page size.

Keep a copy of all three on the same USB stick as the repository. A demonstration
that cannot run scores nothing; a demonstration that falls back gracefully and is
explained honestly still shows understanding.

---

## 8. Do not

- Do not run `git pull` or `npm install` in front of the audience.
- Do not open a terminal in a directory with the `.venv` unactivated and then
  wonder why `uvicorn` is missing.
- Do not show `backend/.env` on screen. Nothing in it is a real secret, but the
  habit is the point.
- Do not claim the rule engine has an accuracy figure. There is no labelled
  evaluation corpus, and saying so is a stronger answer than inventing a number.
