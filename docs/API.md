# PhishGuard — API Reference

19 endpoints. This list was generated from the running application's OpenAPI
schema, not written by hand. The live interactive version is at
<http://localhost:8000/docs> while the backend is running.

**Base URL (local):** `http://localhost:8000`
**Authentication:** `Authorization: Bearer <JWT>` on every endpoint marked *Auth*.

---

## Endpoint summary

| Method | Path | Auth | Roles | Purpose |
|---|---|---|---|---|
| GET | `/` | — | any | Service identity + docs link |
| GET | `/api/health` | — | any | Liveness probe |
| GET | `/health` | — | any | Liveness **+ live database connectivity** |
| GET | `/system/database-status` | — | any | Active engine (PostgreSQL vs SQLite); scheme only, never credentials |
| POST | `/api/auth/login` | — | any | JSON login → JWT + user |
| POST | `/api/auth/token` | — | any | OAuth2 password form (powers Swagger *Authorize*) |
| GET | `/api/auth/me` | Auth | any | Current user |
| GET | `/api/emails` | Auth | any | List emails (staff see only their own) |
| POST | `/api/emails` | Auth | analyst, admin | Ingest + score a new email |
| GET | `/api/emails/{email_id}` | Auth | any | Email detail incl. score reasons |
| POST | `/api/emails/{email_id}/quarantine` | Auth | analyst, admin | Hold the email |
| POST | `/api/emails/{email_id}/release` | Auth | analyst, admin | Deliver the email |
| POST | `/api/emails/{email_id}/confirm-phishing` | Auth | analyst, admin | Confirm as phishing |
| POST | `/api/emails/{email_id}/feedback` | Auth | analyst, admin | Record analyst feedback |
| GET | `/api/release-requests` | Auth | any | List requests (staff see only their own) |
| POST | `/api/release-requests` | Auth | **staff only** | Request release of a held email addressed to the caller |
| POST | `/api/release-requests/{request_id}/decision` | Auth | analyst, admin | Approve or deny |
| GET | `/api/audit-logs` | Auth | analyst, admin | Read the audit trail |
| GET | `/api/dashboard/stats` | Auth | any | Aggregate statistics (role-scoped) |

---

## Authentication

### `POST /api/auth/login`

```json
{ "email": "analyst@phishguard.local", "password": "Analyst@123" }
```

**200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs…",
  "token_type": "bearer",
  "user": { "id": 2, "email": "analyst@phishguard.local",
            "full_name": "Sam Analyst", "role": "analyst", "is_active": true }
}
```

| Status | When |
|---|---|
| 401 | Unknown address **or** wrong password — deliberately the same response and message so the endpoint cannot be used to discover which accounts exist |
| 403 | Account is deactivated (`is_active = false`) |
| 422 | Missing or over-long field |
| 429 | More than `LOGIN_MAX_ATTEMPTS` failures from this IP inside `LOGIN_WINDOW_SECONDS`; includes a `Retry-After` header |

The password hash is never present in any response.

---

## Emails

### `GET /api/emails`

| Query | Type | Notes |
|---|---|---|
| `status` | string | `inbox` · `quarantined` · `released` · `confirmed_phishing` · `safe` |
| `risk_level` | string | `low` · `medium` · `high` · `critical` |
| `search` | string | Matches subject or sender. `%` and `_` are escaped and matched literally |

Sorted by `risk_score` descending, then `received_at` descending.
**Staff receive only emails whose `recipient` is their own address** — enforced
server-side, not in the UI.

### `POST /api/emails` — ingest and score

```json
{
  "sender": "security@paypa1-support.com",
  "sender_name": "PayPal Security",
  "recipient": "staff@phishguard.local",
  "subject": "Urgent: verify your account within 24 hours",
  "body": "Dear customer, we detected unusual activity… http://198.51.100.23/login"
}
```

**201** — the rule engine scores the message on arrival, and `high`/`critical`
results are quarantined automatically:

```json
{
  "id": 9, "message_id": "<ingest-4f2a…@phishguard.local>",
  "risk_score": 80, "risk_level": "critical", "status": "quarantined",
  "auth_spf": "fail", "auth_dkim": "fail", "auth_dmarc": "fail",
  "ai_generated": true,
  "reasons": [
    "Display name impersonates 'paypal' but domain is 'paypa1-support.com'.",
    "Urgency / pressure language: verify now, within 24 hours.",
    "Requests credentials / sensitive data: confirm your password.",
    "Link points directly to a raw IP address.",
    "Copy uses templated phrasing typical of mass phishing."
  ]
}
```

**Input constraints** (mirroring the column widths in `database/schema.sql`):

| Field | Rule |
|---|---|
| `sender`, `recipient` | required, valid address form, ≤ 320 chars, lowercased |
| `sender_name` | optional, ≤ 255 chars |
| `subject` | optional, ≤ 500 chars |
| `body` | optional, ≤ 100 000 chars |

### Analyst actions

`POST /api/emails/{id}/quarantine` · `/release` · `/confirm-phishing` · `/feedback`

Body: `{ "verdict": "phishing", "feedback": "optional note" }` (both optional,
except `feedback` which is required for the feedback endpoint).

| Status | When |
|---|---|
| 200 | Applied; the updated email is returned |
| 403 | Caller is `staff` |
| 404 | No such email |
| 409 | The email is **already** in the target status — nothing changed, so no review or audit row is written |
| 409 | The action is not valid from the email's current status (see the table below); the message names the states it *is* valid from |
| 422 | `feedback` missing/blank on the feedback endpoint, or a field is over-long |

Each successful action writes one `analyst_reviews` row **and** one `audit_logs`
row. A refused action writes **neither**, and does not change the status.

#### Valid transitions

The server accepts an action only from the states in which it is meaningful.
The rules live in `backend/app/transitions.py`.

| Action | Valid from | Moves to |
|---|---|---|
| `quarantine` | `inbox`, `released`, `safe` | `quarantined` |
| `release` | `quarantined`, `confirmed_phishing` | `released` |
| `confirm-phishing` | any status except `confirmed_phishing` | `confirmed_phishing` |
| `feedback` | any status | *(no change)* |

`quarantine` is not valid from `confirmed_phishing`, because that would replace a
stronger verdict with a weaker one. Example refusal:

```json
{
  "error": {
    "code": 409,
    "message": "Cannot 'release' an email with status 'inbox'. This action applies only to email in: quarantined, confirmed_phishing.",
    "request_id": "…"
  }
}
```

---

## Release requests

### `POST /api/release-requests`

```json
{ "email_id": 1, "reason": "I was expecting this invoice from our vendor." }
```

**Staff only.** Raising a request is the recipient's action. An analyst can
release an email directly, so there is no workflow in which they need to ask for
one; allowing it also let a request be filed in a recipient's name. Analysts and
admins keep full read access to the queue and remain the only roles that can
*decide* a request.

| Status | When |
|---|---|
| 201 | Created with `status: "pending"` |
| 403 | Caller is not `staff`, **or** the email is not addressed to the caller |
| 404 | No such email |
| 409 | The email is not held (`quarantined`/`confirmed_phishing`), **or** the caller already has a pending request for it |
| 422 | `reason` shorter than 10 characters (after trimming) or longer than 2000 |

### `POST /api/release-requests/{id}/decision`

```json
{ "status": "approved", "review_note": "Verified with the vendor." }
```

`status` must be exactly `approved` or `denied`.

| Status | When |
|---|---|
| 200 | Decision recorded. `approved` also sets the email to `released` and writes an `analyst_reviews` row |
| 403 | Caller is `staff` |
| 404 | No such request |
| 409 | Already decided |
| 409 | `approved`, but the email is no longer in a releasable state — for example an analyst released or delivered it while the request sat in the queue. The request stays `pending`. Denial is still permitted, because it changes no email status |
| 422 | `status` is not one of the two permitted values |

---

## Oversight

### `GET /api/audit-logs` — analyst/admin only

| Query | Default | Notes |
|---|---|---|
| `action` | — | Exact-match filter |
| `limit` | 200 | Maximum 1000 |

```json
[{
  "id": 12, "user_id": 2, "actor_email": "analyst@phishguard.local",
  "action": "confirm_phishing", "entity_type": "email", "entity_id": 1,
  "details": "confirm_phishing on email 'Urgent: Your account has been suspended'",
  "ip_address": "127.0.0.1", "created_at": "2026-08-05T10:14:22Z"
}]
```

Actions recorded: `login`, `ingest_email`, `quarantine`, `release`,
`confirm_phishing`, `feedback`, `release_request_created`,
`release_request_approved`, `release_request_denied`.

### `GET /api/dashboard/stats`

```json
{
  "total_emails": 8, "quarantined": 3, "confirmed_phishing": 1,
  "released": 0, "safe": 4, "pending_requests": 1,
  "by_level": { "low": 3, "medium": 1, "high": 3, "critical": 1 },
  "avg_risk_score": 41.5,
  "recent_high_risk": [ /* up to 5 EmailBase objects */ ]
}
```

Every figure is scoped to the caller's role: staff see statistics for their own
mailbox only.

---

## Error format

All errors use one envelope:

```json
{
  "error": {
    "code": 409,
    "message": "You already have a pending release request for this email.",
    "details": null,
    "request_id": "8c1e0f7a-…"
  }
}
```

`details` carries a field-level list for 422 responses:

```json
{ "error": { "code": 422,
  "message": "reason: String should have at least 10 characters",
  "details": [{ "field": "reason", "message": "String should have at least 10 characters" }],
  "request_id": "…" } }
```

`request_id` also appears in the `X-Request-ID` response header and in the
server log, so a user-visible error can be traced to its log line.

| Code | Meaning |
|---|---|
| 400/422 | Invalid input |
| 401 | Missing, malformed, expired or wrongly-signed token; bad credentials |
| 403 | Authenticated but not permitted (wrong role, or another user's data) |
| 404 | Resource does not exist |
| 409 | Conflicts with current state (already decided, already in that status, duplicate request) |
| 429 | Rate-limited |
| 503 | Database unavailable or rejected the operation |
| 500 | Unforeseen server fault — generic message, full traceback in the log only |
| 503 | Database unavailable or rejected the operation |

## Response headers

| Header | Value |
|---|---|
| `X-Request-ID` | Correlation id for this request |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |
