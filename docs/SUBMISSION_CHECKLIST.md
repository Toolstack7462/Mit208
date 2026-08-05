# PhishGuard — Submission Checklist

Against the MIT208 Assessment 3 requirements. Each item says how to verify it
rather than simply asserting it is done.

Legend: **[x]** done and verifiable · **[ ]** still requires the author

---

## 1. Prototype — repository and code

- [x] **Complete source code** — `backend/`, `frontend/`, `database/`
- [x] **Dependency files** — `backend/requirements.txt`, `requirements-dev.txt`,
      `frontend/package.json` + `package-lock.json`
- [x] **Installs on a current Python** — verified on 3.11–3.14; CI matrix covers
      3.11, 3.12 and 3.13. Previously impossible (see BUG-01)
- [x] **Safe configuration template** — `backend/.env.example` and
      `frontend/.env.example`, with no working key or credential
- [x] **No secrets committed** — `.env` and database files are git-ignored; a
      secret scan found no keys, tokens or private data
- [x] **Database setup** — `database/schema.sql` (DDL with constraints),
      `database/seed_data.sql`, and `python -m app.seed --reset`
- [x] **README** — purpose, problem, features, architecture, stack, installation,
      configuration, how to run, test accounts, testing, limitations, AI-use note
- [x] **Meaningful commit history** — work committed in separate, purposeful
      commits rather than one bulk upload
- [ ] **Final release `v1.0-final`** — tag pushed; publish the release notes on
      GitHub and paste the link into the report title page and slide 1
- [ ] **Passing GitHub Actions run** — open the Actions tab and confirm the run
      for the final commit is green
- [ ] **Repository accessible to the lecturer** until marking and moderation are
      complete

## 2. Working prototype

- [x] **Core workflow end to end** — ingest → score → quarantine → analyst
      review → staff request → analyst decision → release → audit.
      Proven by 20/20 live checks in `backend/smoke_test.py`
- [x] **All modules integrated** — React frontend, FastAPI backend and the
      database exchange data over HTTP; verified by the smoke workflow
- [x] **Handles realistic input** — validation, meaningful error messages and
      edge cases; see `docs/TESTING.md` sections 6 and the 422/409 cases
- [x] **Runs on a clean machine** — documented setup steps; `npm install`,
      `npm test` and `npm run build` all verified
- [ ] **One local PostgreSQL run** — create the database, apply
      `database/schema.sql`, seed, and screenshot `/system/database-status`
      showing `"engine": "postgresql"`. CI already tests PostgreSQL 16, so this
      is corroboration rather than the only evidence

## 3. Testing evidence

- [x] **Positive test of each core function** — 110 backend tests, 69 frontend tests
- [x] **Invalid-input tests** — blank, malformed, over-long and whitespace-only
      input across every write endpoint
- [x] **Error-handling evidence** — consistent error envelope with a traceable
      `request_id`; the UI shows a retryable message instead of an empty screen
- [x] **Integration evidence** — 20 live checks against a running server and a
      real database file
- [x] **Security/privacy evidence** — `docs/SECURITY.md` maps each control to the
      test that proves it
- [x] **Usability evidence** — labelled screenshots of every core screen, plus
      accessibility-driven tests that locate fields by their labels
- [x] **Regression evidence** — named regression tests for BUG-01, BUG-04,
      BUG-05, BUG-09, BUG-12 and BUG-15
- [x] **Bug log with at least two meaningful problems** — 15 entries, each
      reproduced first, then fixed, then locked in by a test
- [x] **Coverage measured** — 89% backend statement coverage (805/909)
- [x] **ML/AI expectations** — not applicable and stated as such: there is no
      trained model, so no accuracy metric is claimed anywhere

## 4. Report (PDF)

- [x] Follows the required structure, every section within its word allocation
- [x] Approximately 1,665 body words, excluding title page, references and
      appendices
- [x] Harvard referencing, Australian/British English
- [x] Architecture diagram and data-model figure included
- [x] Verified test figures — no superseded or unsupported number remains
- [x] Honest limitations section
- [x] AI-use declaration present
- [ ] **Insert your name, student ID, lecturer and submission date** on the
      title page
- [ ] **Insert the `v1.0-final` release link** on the title page
- [ ] **Read the reflection and AI declaration aloud** and adjust anything that
      is not how you would put it. You must be able to defend every sentence

## 5. Technical presentation (PPTX)

- [x] Ten technical slides, not a marketing deck
- [x] Architecture, technology stack and implementation journey covered
- [x] Testing and security slide carries the verified figures
- [x] Real product screenshots from the running application
- [x] Results and limitations stated plainly
- [x] Speaker notes on all ten slides
- [ ] **Insert your name and student ID** on slide 1
- [ ] **Insert the release link** on slides 1 and 10

## 6. Walkthrough video (3–4 minutes)

- [x] 4:00 capture of the actual running software, not slides
- [x] Paced to the five segments in the brief; timeline in
      `evidence/video/TIMING.md`
- [x] Readable resolution (1280x720, H.264 MP4)
- [x] No password, key or private data exposed
- [x] Narration script and shot list drafted
- [ ] **Record the narration in your own voice** over
      `evidence/video/PhishGuard_Walkthrough.mp4`, or re-record the whole thing
      live with OBS using the shot list
- [ ] **Confirm the exported file plays with audible sound** before submitting

## 7. Prototype access information

- [x] Local setup instructions that work from a clean clone
- [x] Test credentials documented (synthetic `.local` accounts)
- [x] No real password, key or private dataset published
- [ ] Deployed URL — **not applicable**; state in Moodle that the prototype runs
      locally and will be demonstrated live

## 8. Before you submit

- [ ] Open the repository link in a **private/incognito** window and confirm it
      loads
- [ ] Open the release link, the report PDF and the video link the same way
- [ ] Confirm the report PDF opens and is readable
- [ ] Keep an unchanged backup of everything submitted until results and
      moderation are finished
- [ ] Prepare for the live showcase: have the app, sample data and a test account
      ready, plus an offline backup in case the network fails
- [ ] Be able to identify the incomplete features honestly — the DistilBERT
      placeholder, the simulated SPF/DKIM/DMARC values, and the absence of live
      mail ingestion

---

## Fastest way to verify the prototype yourself

```bash
git clone https://github.com/Toolstack7462/Mit208.git && cd Mit208

# Backend
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into SECRET_KEY
python -m pytest                      # expect: 110 passed
python -m app.seed --reset
uvicorn app.main:app --port 8000

# Frontend, in a second terminal
cd frontend && npm install
npm test                              # expect: 69 passed
npm run dev                           # http://localhost:5173

# End-to-end, in a third terminal
cd backend && python smoke_test.py    # expect: ALL 20/20 CHECKS PASSED
```

Sign in as `analyst@phishguard.local` / `Analyst@123`.
