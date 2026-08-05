# PhishGuard — Bug and Problem Log

Defects found during a structured review of the working prototype, and how each
was fixed. Every entry was **reproduced before being fixed** and has a named
regression test that fails against the old code and passes against the new.

The reproduction commands assume the setup in the README.

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-01](#bug-01) | Critical | Dependencies / reproducibility | Fixed |
| [BUG-02](#bug-02) | High | Release-request workflow | Fixed |
| [BUG-03](#bug-03) | High | Input validation / cross-database consistency | Fixed |
| [BUG-04](#bug-04) | High | Frontend error handling | Fixed |
| [BUG-05](#bug-05) | High | Secret management | Fixed |
| [BUG-06](#bug-06) | Medium | Input validation | Fixed |
| [BUG-07](#bug-07) | Medium | Data consistency / audit accuracy | Fixed |
| [BUG-08](#bug-08) | Medium | Email ingestion | Fixed |
| [BUG-09](#bug-09) | Medium | Search behaviour | Fixed |
| [BUG-10](#bug-10) | Medium | Authentication hardening | Fixed |
| [BUG-11](#bug-11) | Low | Accessibility | Fixed |
| [BUG-12](#bug-12) | High | Reliability / stored-data parsing | Fixed |
| [BUG-13](#bug-13) | Medium | Database integrity | Fixed |
| [BUG-14](#bug-14) | Medium | Token and password handling | Fixed |
| [BUG-15](#bug-15) | Low | Notification correctness | Fixed |

---

## BUG-01
### `pip install -r requirements.txt` fails on Python 3.13 and 3.14

**Severity:** Critical — nobody on a current Python could run the project at all.

**Symptom**

```
ERROR: Failed to build 'psycopg2-binary' when getting requirements to build wheel
...
ERROR: Failed building wheel for pydantic-core
error: failed-wheel-build-for-install
```

**Investigation**

The requirements file pinned exact patch releases: `psycopg2-binary==2.9.10` and
`pydantic==2.10.4`. Both distribute pre-compiled binary wheels, but only for the
interpreter versions that existed when that patch was released. On Python 3.13+
pip finds no matching wheel, falls back to compiling from source, and fails
without a C toolchain and PostgreSQL headers. Checking the index confirmed
`psycopg2-binary` only gained Python 3.14 wheels in **2.9.12**.

This is the kind of defect that never shows up on the original developer's
machine — it only appears for anyone else.

**Fix** — `backend/requirements.txt`, `backend/requirements-dev.txt`

Switched from `==` to the compatible-release operator `~=`, which holds the
API-compatible minor version but allows a newer patch that ships a wheel for the
interpreter in use:

```diff
-psycopg2-binary==2.9.10
-pydantic==2.10.4
+psycopg2-binary~=2.9.12
+pydantic~=2.13.4
```

**Verification**

```bash
cd backend && pip install -r requirements-dev.txt   # completes on Python 3.14
python -m pytest                                    # 75 passed
```

A CI matrix (`.github/workflows/ci.yml`) now installs and tests on Python 3.11,
3.12 and 3.13, so this cannot silently regress.

---

## BUG-02
### Unlimited duplicate release requests, on any email, with no justification

**Severity:** High — corrupted the analyst work queue.

**Symptom**

Three identical POSTs to `/api/release-requests` all returned `201`, creating
three pending rows for the same email. Requests were also accepted for emails
that had never been quarantined, and with a completely empty `reason` — even
though the UI prompts "Tell the analyst why this email is safe to release."

Reproduced with a probe test:

```
DUPLICATE REQUESTS -> 201, 201, 201
probe empty reason  -> 201 {"reason":"", "status":"pending", …}
probe release-request on INBOX email -> 201
```

**Investigation**

`create_request` in `backend/app/routers/requests.py` checked only that the email
existed and, for staff, that they were the recipient. It never checked the
email's status, never looked for an existing open request, and
`ReleaseRequestCreate.reason` had a default of `""` with no minimum length. An
analyst reviewing the queue would see repeated rows with no stated reason and no
way to tell which was current.

**Fix**

1. `backend/app/routers/requests.py` — reject a request when the email is not
   held (`409`), and when the same user already has a pending request for it
   (`409`). Denied requests do **not** block a later resubmission, so a genuine
   second attempt after new information is still possible.
2. `backend/app/schemas.py` — `reason` is now required, minimum 10 characters
   after trimming, maximum 2000.
3. `frontend/src/pages/StaffPortal.jsx` — Submit stays disabled until the reason
   is long enough, a character counter and inline message explain the rule, and
   the button is short-circuited for emails that already have an open request.

**Verification** — `backend/tests/test_release_workflow.py` (14 tests), including
`test_duplicate_pending_request_is_rejected`,
`test_a_new_request_is_allowed_after_the_previous_one_was_denied`,
`test_request_against_a_delivered_email_is_rejected`, plus
`frontend/src/pages/StaffPortal.test.jsx` (7 tests). Live checks 18 and 19 in
`smoke_test.py`.

---

## BUG-03
### Over-long input is accepted on SQLite and crashes on PostgreSQL

**Severity:** High — a defect invisible in local testing that only appears on the
assessed database.

**Symptom**

```
probe oversized subject (2000 chars) -> 201
```

`email_records.subject` is `VARCHAR(500)`. SQLite ignores declared string
lengths, so the value was stored intact and the request succeeded. PostgreSQL
enforces the width and raises `StringDataRightTruncation`, which surfaced to the
client as an opaque HTTP 500.

**Investigation**

`EmailCreate` in `backend/app/schemas.py` declared bare `str` fields with no
constraints, so nothing between the HTTP request and the `INSERT` bounded the
input. Because day-to-day development used the SQLite fallback while PostgreSQL
is the official target, the two engines behaved differently for the same request
— the worst possible split.

The same absence of constraints also meant blank sender and recipient were
accepted (`probe blank sender/recipient -> 201`), storing unusable records.

**Fix** — `backend/app/schemas.py`

Every input field now declares a length that mirrors its column, plus format
validation for addresses, with the limits stated as named constants next to a
comment pointing at `models.py`:

```python
MAX_ADDRESS, MAX_NAME, MAX_SUBJECT, MAX_BODY = 320, 255, 500, 100_000

class EmailCreate(BaseModel):
    sender: str = Field(min_length=3, max_length=MAX_ADDRESS)
    subject: str = Field(default="", max_length=MAX_SUBJECT)
    ...
```

Over-long input is now a `422` with a field-level message on **both** engines,
and never reaches the database.

**Verification** — `backend/tests/test_validation.py`:
`test_oversized_subject_rejected_not_500`,
`test_subject_at_exactly_the_column_limit_is_accepted` (boundary),
`test_blank_sender_and_recipient_rejected`, `test_malformed_sender_rejected`.
The `backend-postgres` CI job seeds and verifies against a real PostgreSQL 16
container. Live checks 9–11 in `smoke_test.py`.

---

## BUG-04
### A failed API call renders as "no data" instead of an error

**Severity:** High — the UI actively misinformed the user.

**Symptom**

With the backend stopped, the Audit Logs page displayed the table header and
**"No audit entries."** — identical to a genuinely empty audit trail. The
Dashboard was worse: it stayed on "Loading…" indefinitely.

**Investigation**

```jsx
// AuditLogs.jsx — before
useEffect(() => {
  api.get("/api/audit-logs").then((r) => setLogs(r.data));   // no rejection handler
}, []);
```

`AuditLogs.jsx` had no `.catch()` at all, so the promise rejected unhandled and
`logs` stayed `[]`, which rendered the empty state. `Dashboard.jsx` guarded on
`if (!stats) return <Loading/>`, and since the failed request never set `stats`,
that spinner was permanent. `Inbox.jsx` and `StaffPortal.jsx` had the same
unhandled rejection on their initial load and on the email-detail fetch.

The rubric requires evidence that the system "responds meaningfully when an
operation fails", and this failed that outright.

**Fix**

1. `frontend/src/lib/errors.js` — new module mapping any Axios failure to a
   readable sentence, including the no-response case ("Cannot reach the
   PhishGuard API. Check that the backend is running on port 8000.") and a
   distinct message for a timeout.
2. `frontend/src/components/StateBlock.jsx` — shared `LoadingBlock`,
   `ErrorBlock` (with a **Try again** button and the `request_id` for tracing)
   and `EmptyBlock`.
3. All four data pages now track explicit `loading` / `error` state and render
   the three states distinctly, so "failed" is never shown as "empty".
4. `backend/app/main.py` — global exception handlers give every error a
   consistent envelope, so there is always a `message` for the UI to display.

**Verification** — `frontend/src/pages/AuditLogs.test.jsx`:
`shows an error instead of a misleading empty table when the API fails`,
`retries the request when the user clicks Try again`,
`shows the genuine empty state when the API returns no rows` (proving the two
cases are now distinguishable). Plus 13 tests in `frontend/src/lib/errors.test.js`.

---

## BUG-05
### A guessable JWT signing key was the built-in default

**Severity:** High — anyone who read the public repository could forge an admin token.

**Symptom**

```
probe secret_key in use -> 'dev-only-change-me-please-0123456789abcdef'
```

**Investigation**

`config.py` declared `secret_key: str = "dev-only-change-me-please-0123456789abcdef"`
as a working default, and `.env.example` shipped that **same literal**. Copying
the template — which the README instructs — produced a deployment whose signing
key is public knowledge. Since `create_access_token` puts `sub` and `role` in the
payload, anyone could mint a valid admin token. Nothing warned about it.

**Fix** — `backend/app/config.py`

A `model_validator` now rejects the placeholder, the old hard-coded literal, and
anything shorter than 32 characters:

- `ENVIRONMENT=production` → **refuses to start**, with the command to generate a
  proper key.
- development → substitutes a random per-process key and logs a warning. Tokens
  stop surviving a restart, which is a visible nudge rather than a silent risk.

`.env.example` now carries a non-functional placeholder
(`CHANGE_ME_GENERATE_A_RANDOM_64_CHAR_SECRET`) and the generation command, and its
`DATABASE_URL` uses `USER:PASSWORD` rather than real-looking credentials.

**Verification** — `backend/tests/test_security.py`:
`test_production_refuses_the_placeholder_secret`,
`test_production_refuses_a_short_secret`,
`test_development_substitutes_a_random_secret_instead_of_the_placeholder`,
`test_the_old_hardcoded_default_is_still_refused` (explicit regression guard).

---

## BUG-06
### Whitespace passed the "feedback is required" check

**Severity:** Medium

**Symptom** — `POST /api/emails/{id}/feedback` with `{"feedback": "     "}`
returned `200` and stored a review with no usable content.

**Investigation** — the route tested `if not payload.feedback`, which is false
for a non-empty whitespace string, so the guard was bypassed.

**Fix** — `backend/app/schemas.py`: a validator on `ReviewAction` normalises a
whitespace-only `verdict`/`feedback` to `None`, so the existing check works
correctly instead of being duplicated per route.

**Verification** — `test_validation.py::test_whitespace_only_feedback_rejected`;
live check 15.

---

## BUG-07
### Repeating an action wrote a review and audit entry for a change that never happened

**Severity:** Medium — it made the audit trail misleading, which defeats its purpose.

**Symptom** — quarantining an already-quarantined email returned `200` and
appended another `analyst_reviews` row plus another `audit_logs` row, implying a
state change had occurred.

**Fix** — `backend/app/routers/emails.py`: `_apply_action` returns `409` when the
email is already in the target status, before any row is written. Separately,
approving a release request now also writes an `analyst_reviews` row, so every
status change on an email has a matching review regardless of which path caused
it — previously only direct analyst actions did.

**Verification** — `test_validation.py::test_repeating_an_action_is_rejected`,
`test_release_workflow.py::test_approval_records_an_analyst_review_and_audit_entry`;
live check 13.

---

## BUG-08
### `message_id` was derived from the row count, so concurrent ingests could collide

**Severity:** Medium — a latent uniqueness failure under concurrent use.

**Investigation**

```python
count = db.query(EmailRecord).count()
message_id = f"<demo-{count + 1}-{payload.recipient}>"
```

`message_id` is `UNIQUE`. Two requests interleaving between the `count()` and the
`INSERT` read the same count and generate the same id; the second fails with an
`IntegrityError` surfacing as an opaque 500. Deleting any row reintroduces a
collision for the same reason.

**Fix** — `backend/app/routers/emails.py`: generate
`f"<ingest-{uuid4().hex[:16]}@phishguard.local>"`, removing the dependency on
table state entirely.

**Verification** — `test_validation.py::test_ingested_message_ids_are_unique`.

---

## BUG-09
### `%` in the search box matched every email

**Severity:** Medium

**Investigation** — the search term was interpolated straight into an `ilike`
pattern, so `%` and `_` were treated as SQL wildcards. Searching for "100%"
returned everything. (The query was parameterised, so this was a correctness bug,
not SQL injection.)

**Fix** — `backend/app/routers/emails.py`: escape `\`, `%` and `_` in the term and
pass `escape="\\"` to `ilike`.

**Verification** — `test_validation.py::test_like_wildcard_in_search_is_literal`
and `test_search_finds_a_known_subject` (proving normal search still works).

---

## BUG-10
### Unlimited login attempts, and response timing revealed which accounts exist

**Severity:** Medium

**Investigation** — nothing limited attempts against `/api/auth/login`, so the
demo passwords could be brute-forced offline-fast. Separately, an unknown address
returned before any bcrypt comparison ran while a known address paid the full
hashing cost, making response time a reliable account-enumeration oracle.

**Fix**

- `backend/app/ratelimit.py` — new per-IP limiter counting only **failed**
  attempts in a rolling window; configurable via `LOGIN_MAX_ATTEMPTS` /
  `LOGIN_WINDOW_SECONDS`. Returns `429` with `Retry-After`. A successful login
  clears the counter, so a legitimate user who mistypes once is unaffected.
- `backend/app/security.py` — `dummy_verify()` performs one bcrypt comparison
  against a pre-computed hash when the address is unknown, so both paths take
  comparable time.

Its scope limit is documented rather than hidden: the counters live in process
memory, which suits the single-worker demo but would need Redis across workers.

**Verification** — `backend/tests/test_security.py`:
`test_repeated_failed_logins_are_rate_limited`,
`test_rate_limit_blocks_even_a_correct_password`,
`test_successful_login_clears_the_failure_counter`,
`test_unknown_and_wrong_password_are_indistinguishable`.

---

## BUG-11
### Login inputs had no programmatic labels

**Severity:** Low — an accessibility defect that also made the form untestable.

**Investigation** — the labels were plain `<label>` elements with no `htmlFor`
and the inputs were not nested inside them, so no accessible name was exposed. A
screen reader announced an unlabelled text box, and
`getByLabelText(/password/i)` could not find the field.

**Fix** — `frontend/src/pages/Login.jsx`: `htmlFor`/`id` pairs, `name`,
`type="email"`, correct `autoComplete` values, and `role="alert"` on the error
banner so failures are announced. The release-reason textarea in `StaffPortal.jsx`
gained a label plus `aria-invalid` / `aria-describedby`.

**Verification** — `frontend/src/pages/Login.test.jsx` (7 tests) now locates both
fields by their labels, which is only possible because the association exists.

---

## BUG-12
### One corrupt row made an email permanently unreadable

**Severity:** High — a single bad value cost access to an entire record.

**Symptom**

With `email_records.score_reasons` set to anything that is not valid JSON, the
detail endpoint returned HTTP 500 and the message could not be opened at all,
even though its score, level, sender, subject and body were untouched.

Reproduced by corrupting one row and requesting it:

```
probe malformed score_reasons -> 500
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
```

**Investigation**

`get_email` in `backend/app/routers/emails.py` parsed the column directly:

```python
data["reasons"] = json.loads(email.score_reasons or "[]")
```

`EmailDetailOut` already had a tolerant validator for this field, but that path
was bypassed because the handler overwrote `reasons` with its own bare
`json.loads`. So the tolerance existed in the schema and did nothing.

The consequence is out of proportion to the cause: the explanation is a
convenience, while the score and level — the parts an analyst acts on — live in
their own columns and were perfectly intact.

**Fix** — `backend/app/routers/emails.py`

A `parse_score_reasons` helper that never raises. Invalid JSON yields a
placeholder ("Stored risk explanation could not be read; the recorded score and
level are unchanged.") and logs a warning; valid JSON of an unexpected shape (a
bare string or number) is coerced to a single-item list.

**Verification** — `backend/tests/test_integrity.py`:
`test_corrupt_score_reasons_does_not_make_an_email_unreadable` deliberately
corrupts a row and asserts HTTP 200 with the score, level and body still
correct; `test_email_list_still_works_when_one_row_is_corrupt`; plus four unit
tests over the helper covering valid, empty, malformed and wrong-shape input.

---

## BUG-13
### The database accepted values the application would never produce

**Severity:** Medium — the API was the only thing preventing invalid data.

**Symptom**

A direct write bypassed every rule. Inserting a user with `role='superadmin'`
succeeded, as did an email with `status='deleted'` or `risk_score=1000`:

```
probe direct-write bad role -> ACCEPTED bogus role 'superadmin'
```

**Investigation**

`role`, `status`, `risk_level` and the SPF/DKIM/DMARC fields were plain
`VARCHAR` columns with no `CHECK` constraint, and `risk_score` was an unbounded
`INTEGER`. Any migration, `psql` session or future script could store a value no
code path can interpret — and a bogus role is a privilege question, not a
cosmetic one.

Separately, the "one open release request per user per email" rule lived only in
the API, where the existence check and the `INSERT` are two statements. Two
concurrent submissions could both pass the check.

**Fix** — `backend/app/models.py` and `database/schema.sql`

- `CHECK` constraints on `users.role`, `email_records.status`,
  `email_records.risk_level`, the three authentication-result columns, and
  `risk_score BETWEEN 0 AND 100`.
- A `CHECK` on `staff_release_requests` requiring that a decided request records
  its reviewer and timestamp, and that a pending one does not.
- A **partial unique index** on `(email_id, requested_by) WHERE status =
  'pending'`, which makes the duplicate rule atomic while still allowing a fresh
  request after a previous one was denied.

The permitted values are declared once as module constants so the ORM, the DDL
and the tests cannot drift apart. Both PostgreSQL and SQLite enforce `CHECK`
constraints and partial indexes, so the automated suite exercises them too.

**Verification** — `backend/tests/test_integrity.py` (20 tests), including
`test_database_rejects_an_unknown_role`,
`test_database_rejects_unknown_enumerated_email_values` (parameterised over five
columns), `test_database_rejects_a_risk_score_outside_zero_to_one_hundred`,
`test_database_blocks_a_second_pending_request_for_the_same_email_and_user`,
`test_the_index_only_constrains_pending_rows`, and matching positive tests
proving every documented value is still accepted. The PostgreSQL DDL was
compiled through SQLAlchemy's PostgreSQL dialect to confirm the partial index
emits correctly.

---

## BUG-14
### Tokens carried no identity, and a long password could not be hashed

**Severity:** Medium

**Symptom**

```
probe jwt claims -> ['exp', 'role', 'sub']
probe bcrypt 100-char password -> RAISED ValueError:
    password cannot be longer than 72 bytes
```

**Investigation**

Two separate weaknesses in the same area.

*Tokens.* The payload held only `sub`, `role` and `exp`. There was no `jti`, so
one token could not be distinguished from another in a log and there was nothing
for a future revocation list to key on; no `iat`, so age was unverifiable; and no
`typ`, so any token signed with the same key — a refresh or password-reset token
added later — would be accepted as an API access token.

*Passwords.* bcrypt raises `ValueError` above 72 bytes. `verify_password` caught
it and returned `False`, so login was safe, but `hash_password` did not, and the
login schema permitted 128 characters — a length that could never authenticate.
Truncating to 72 instead would be worse: it would make `"<72 bytes>abc"` and
`"<same 72 bytes>xyz"` the same password.

**Fix** — `backend/app/security.py`, `backend/app/schemas.py`

- Tokens now carry `iat`, `jti` and `typ: "access"`, and `decode_access_token`
  rejects a token whose `typ` is anything else, requires `exp` and `sub`, and
  pins the algorithm allow-list.
- A named `PasswordTooLongError` is raised above 72 bytes rather than truncating,
  with a message that mentions multi-byte characters. `verify_password` still
  never raises. The login schema's maximum is now 72 to match, so an over-long
  submission is a clear 422.

**Verification** — `backend/tests/test_security.py`:
`test_access_token_carries_identifying_claims`,
`test_each_token_has_a_unique_identifier`,
`test_token_of_another_type_is_rejected`,
`test_token_without_the_required_claims_is_rejected`,
`test_expired_token_is_rejected`,
`test_password_longer_than_bcrypt_allows_is_refused_not_truncated`,
`test_verify_password_never_raises_on_an_over_long_input`,
`test_login_with_an_over_long_password_is_a_validation_error`. `security.py` is
now at 100% statement coverage.

---

## BUG-15
### Refusals were announced with a success tick, then vanished early

**Severity:** Low — but it made the interface contradict itself.

**Symptom**

Found by reading the captured screenshots rather than the code. Declining a
duplicate release request showed the message *"You already have a pending release
request for this email"* next to a **green success tick**.

Fixing that surfaced a second, worse problem: after a successful submission
followed quickly by a refusal, the refusal disappeared from the screen after
about a second, so the user never saw why the action failed.

**Investigation**

Each page kept its own `toast` string and rendered a hard-coded
`CheckCircle2` icon, so there was no way to express failure. The first fix added
a tone, but the shared `useToast` hook called `setTimeout` without cancelling the
previous one — so the earlier success toast's timer was still pending and cleared
the newer error message when it fired.

**Fix** — `frontend/src/components/Toast.jsx`

One shared `Toast` component plus a `useToast` hook, used by the inbox, staff
portal and release-request pages. Errors render red with a warning icon and
`role="alert"` / `aria-live="assertive"`; successes stay neutral with
`role="status"` / `aria-live="polite"`. The hook keeps the pending timer in a ref
and clears it before starting a new one, gives errors a longer dwell, and clears
the timer on unmount.

**Verification** — `frontend/src/components/Toast.test.jsx` (8 tests), including
`announces a failure as an assertive alert, not a status`,
`keeps an error visible when it replaces a success mid-countdown` (the timer
regression) and `eventually dismisses the error on its own longer timeout`. The
corrected behaviour is visible in
`evidence/screenshots/12-duplicate-request-blocked.png`.

---

## Problems investigated and deliberately **not** changed

Recorded for honesty — these were considered and consciously left alone.

| Observation | Decision |
|---|---|
| JWT is stored in `localStorage`, so it is readable by any script that achieves XSS | Kept. The alternative (`HttpOnly` cookie) needs CSRF protection and a same-site deployment, which is a larger change than this MVP warrants. Documented as a known limitation in `docs/SECURITY.md` and the README. |
| Tokens now carry a `jti`, so revocation is *possible* — but no revocation list exists | Not implemented. A deny-list needs shared storage to be meaningful across restarts and workers, which is the same infrastructure the rate limiter would need. The `jti` is the groundwork; the feature is listed as future work rather than implied to work. |
| The login page pre-fills the demo analyst credentials | Kept deliberately. These are synthetic accounts on a `.local` domain, the rubric asks for test credentials, and one-click sign-in matters for the live showcase. It would be wrong in a real product and is labelled as demo-only. |
| `status`, `role`, `risk_level` are `VARCHAR`, not `ENUM`/`CHECK` | Not changed. The API constrains all three, and adding database enums would mean a migration path this MVP does not have. Listed as future work. |
| The audit log has no pagination beyond `limit` | Not changed. `limit` is capped at 1000, which comfortably exceeds the demo data. Noted as future work. |
| `ml_model.py` raises `NotImplementedError` | Correct as-is. It is a documented integration point for future work, is not reachable from any running path, and is stated as unimplemented in the README, the architecture doc and the report rather than being implied to work. |
