# Screenshot evidence

Captured from the running application by `evidence/capture_screenshots.py` (Playwright + Chromium, 1600x1000 at 2x). No image is edited or mocked.

| # | File | What it shows |
|---|---|---|
| 01 | `01-login.png` | Sign-in screen with role-based demo accounts |
| 02 | `02-login-invalid-credentials.png` | Invalid credentials rejected with the API's own message (HTTP 401) |
| 03 | `03-analyst-dashboard.png` | Analyst dashboard: live statistics, weekly threat distribution and risk mix |
| 04 | `04-analyst-inbox.png` | Email inbox sorted by risk score, with filter tabs and status badges |
| 05 | `05-inbox-high-risk-filter.png` | Inbox filtered to high-risk messages only |
| 06 | `06-email-detail-explainable-score.png` | Email detail: risk score with the specific indicators that produced it, plus simulated SPF/DKIM/DMARC results |
| 07 | `07-audit-log.png` | Append-only audit trail recording actor, action, entity, detail and IP address |
| 08 | `08-release-requests-analyst.png` | Release-request queue awaiting an analyst decision |
| 09 | `09-staff-portal.png` | Staff portal showing only the signed-in user's own mail |
| 10 | `10-release-request-validation.png` | Release request blocked until an adequate justification is supplied (mirrors the backend's 10-character rule) |
| 11 | `11-release-request-submitted.png` | Release request accepted and confirmed to the staff member |
| 12 | `12-duplicate-request-blocked.png` | A second request for the same email is refused (one open request per user) |
| 13 | `13-release-request-approved.png` | Analyst approval recorded; the underlying email is released in the same transaction |
| 14 | `14-audit-after-approval.png` | Audit trail after the approval, showing release_request_approved |
| 15 | `15-staff-denied-audit-access.png` | Staff navigating to /audit is redirected to the dashboard; the API also returns 403 independently of the UI |
| 16 | `16-error-state-api-unreachable.png` | Dashboard when the API cannot be reached: an explicit, retryable error instead of an empty or permanently loading screen |
| 17 | `17-openapi-docs.png` | Interactive OpenAPI documentation generated from the FastAPI application |

## PostgreSQL evidence

Captured by `evidence/capture_postgres_evidence.py` against the application running on PostgreSQL 16.6, which the script verifies before taking a single image.

| File | What it shows |
|---|---|
| `18-postgresql-database-status.png` | The API reporting PostgreSQL as the live engine, with using_fallback false — credentials are never included, only the URL scheme |
| `19-postgresql-dashboard.png` | The analyst dashboard served from PostgreSQL — the same workflow as the SQLite captures, on the assessed target database |
| `20-postgresql-openapi.png` | OpenAPI documentation served by the backend while connected to PostgreSQL |
