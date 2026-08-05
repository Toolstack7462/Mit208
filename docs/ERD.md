# PhishGuard — Data Model / ERD

Five tables. Definitive DDL: [`database/schema.sql`](../database/schema.sql).
ORM definitions: [`backend/app/models.py`](../backend/app/models.py).

---

## Entity-relationship diagram

```mermaid
erDiagram
    USERS ||--o{ ANALYST_REVIEWS : "performs"
    USERS ||--o{ STAFF_RELEASE_REQUESTS : "raises"
    USERS ||--o{ STAFF_RELEASE_REQUESTS : "reviews"
    USERS ||--o{ AUDIT_LOGS : "is actor of"
    EMAIL_RECORDS ||--o{ ANALYST_REVIEWS : "is reviewed by"
    EMAIL_RECORDS ||--o{ STAFF_RELEASE_REQUESTS : "is subject of"

    USERS {
        int         id              PK
        varchar255  email           UK "unique, indexed, lowercased"
        varchar255  full_name
        varchar255  hashed_password "bcrypt, never returned by the API"
        varchar32   role            "analyst | staff | admin"
        boolean     is_active       "checked on every request"
        timestamptz created_at
    }

    EMAIL_RECORDS {
        int         id            PK
        varchar255  message_id    UK "random per ingest"
        varchar320  sender
        varchar255  sender_name   "nullable; display name"
        varchar320  recipient     "indexed; scopes staff visibility"
        varchar500  subject
        text        body
        varchar32   status        "inbox | quarantined | released | confirmed_phishing | safe"
        int         risk_score    "0-100"
        varchar16   risk_level    "low | medium | high | critical"
        text        score_reasons "JSON array of explanations"
        varchar8    auth_spf      "pass | fail | none (simulated)"
        varchar8    auth_dkim
        varchar8    auth_dmarc
        boolean     ai_generated
        timestamptz received_at
        timestamptz created_at
    }

    ANALYST_REVIEWS {
        int         id         PK
        int         email_id   FK "-> email_records.id, ON DELETE CASCADE"
        int         analyst_id FK "-> users.id"
        varchar32   action     "quarantine | release | confirm_phishing | feedback"
        varchar32   verdict    "phishing | safe | unsure"
        text        feedback
        timestamptz created_at
    }

    STAFF_RELEASE_REQUESTS {
        int         id           PK
        int         email_id     FK "-> email_records.id, ON DELETE CASCADE"
        int         requested_by FK "-> users.id"
        text        reason       "min 10 chars, enforced by the API"
        varchar16   status       "pending | approved | denied"
        int         reviewed_by  FK "-> users.id, nullable"
        text        review_note
        timestamptz created_at
        timestamptz reviewed_at
    }

    AUDIT_LOGS {
        int         id          PK
        int         user_id     FK "-> users.id, nullable"
        varchar255  actor_email "denormalised, survives user changes"
        varchar64   action
        varchar64   entity_type "email | release_request | user"
        int         entity_id
        text        details
        varchar64   ip_address
        timestamptz created_at
    }
```

---

## Relationships

| From | To | Cardinality | Meaning |
|---|---|---|---|
| `users` → `analyst_reviews` | `analyst_id` | 1 : N | One analyst performs many reviews |
| `users` → `staff_release_requests` | `requested_by` | 1 : N | One staff member raises many requests |
| `users` → `staff_release_requests` | `reviewed_by` | 1 : N | One analyst decides many requests (nullable until decided) |
| `users` → `audit_logs` | `user_id` | 1 : N | One user is the actor of many events |
| `email_records` → `analyst_reviews` | `email_id` | 1 : N | One email accumulates many reviews |
| `email_records` → `staff_release_requests` | `email_id` | 1 : N | One email may be the subject of several requests over time |

`staff_release_requests` has **two** foreign keys into `users`, which is why the
ORM relationships in `models.py` declare `foreign_keys=` explicitly.

---

## Indexes

Defined in `database/schema.sql` and mirrored by the ORM:

| Table | Index | Why |
|---|---|---|
| `users` | `email` (unique) | Login lookup on every authentication |
| `email_records` | `message_id` (unique) | Prevents duplicate ingestion |
| `email_records` | `status` | The inbox filters on status |
| `email_records` | `recipient` | Staff visibility scoping runs on every list request |
| `analyst_reviews` | `email_id`, `analyst_id` | Review history lookups |
| `staff_release_requests` | `status`, `requested_by` | The pending queue and the duplicate-request check |
| `audit_logs` | `action`, `created_at`, `user_id` | The audit view filters by action and sorts by time |

---

## Integrity rules

**Enforced by the database**

- `users.email` and `email_records.message_id` are unique.
- All foreign keys are declared; deleting an email cascades to its reviews and
  release requests, so no orphan rows remain.
- `NOT NULL` on every column the application always populates.
- `VARCHAR(n)` widths bound every text column except `body`, `details`,
  `reason`, `review_note`, `feedback` and `score_reasons` (all `TEXT`).

**Enforced by the API** (`schemas.py` + the routers)

- Input length constraints mirror the column widths, so an over-long value is a
  422 rather than a database error. See `docs/BUG_LOG.md`, BUG-03.
- `sender` and `recipient` must be syntactically valid addresses and are
  lowercased before storage.
- A release request requires a reason of at least 10 characters.
- A release request is only valid against an email whose status is
  `quarantined` or `confirmed_phishing`.
- At most one *pending* release request per (email, user) pair.
- A decided request cannot be decided again (409).
- An analyst action that would not change the status is rejected (409), so no
  duplicate review or audit row is written for a state change that never
  happened.

**Now also enforced by the database** (added after BUG-13)

- `CHECK` constraints restrict `users.role`, `email_records.status`,
  `email_records.risk_level` and the three authentication-result columns to their
  documented values, and bound `risk_score` to 0–100.
- A `CHECK` on `staff_release_requests` requires a decided request to record its
  reviewer and timestamp, and a pending one not to.
- A **partial unique index** on `(email_id, requested_by) WHERE status =
  'pending'` makes "at most one open request per user per email" atomic, so two
  concurrent submissions cannot both succeed.

The permitted values are declared once as constants in `backend/app/models.py`,
so the ORM, `database/schema.sql` and the tests cannot drift apart.

**Still not enforced**

- The columns are `VARCHAR` with `CHECK` constraints rather than PostgreSQL
  `ENUM` types. That is a deliberate trade-off: `CHECK` constraints work
  identically on SQLite, so the automated suite exercises the same rules the
  assessed database applies. Moving to native enumerated types is future work.
