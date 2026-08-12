"""Capture labelled screenshots of the REAL running PhishGuard application.

This script drives a real Chromium browser against the running frontend and
backend. Nothing is mocked or drawn: every image is the application's own output
at that moment. Re-run it after any UI change so the evidence never goes stale.

Prerequisites (see README):
    backend :  python -m app.seed --reset  &&  uvicorn app.main:app --port 8000
    frontend:  npm run dev                                  (port 5173)
    tooling :  pip install playwright  &&  playwright install chromium

Usage:
    python evidence/capture_screenshots.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
API = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent / "screenshots"

# 1600x1000 at deviceScaleFactor 2 renders at 3200x2000, which stays sharp when a
# slide or report scales it down. Wide enough for the full sidebar + content.
VIEWPORT = {"width": 1600, "height": 1000}
SCALE = 2

ANALYST = ("analyst@phishguard.local", "Analyst@123")
STAFF = ("staff@phishguard.local", "Staff@123")

shots: list[tuple[str, str]] = []


def shot(page, name: str, description: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(700)          # let transitions and charts settle
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    shots.append((f"{name}.png", description))
    print(f"  captured {name}.png  -- {description}")


def engine() -> str:
    """Which database the application is actually serving from, for the index.

    Recorded rather than enforced: these captures are legitimate on either engine.
    It is written into INDEX.md so the evidence states its own provenance instead
    of relying on a sentence in the README that nothing checks.
    """
    try:
        with urllib.request.urlopen(f"{API}/system/database-status", timeout=15) as r:
            status = json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError):
        return "not reported (the /system/database-status endpoint was unreachable)"
    return f"{status.get('type', status.get('engine'))} (using_fallback={status.get('using_fallback')})"


def sign_out(page) -> None:
    """Clear the stored session so the next login starts clean.

    localStorage is per-origin, so this must run on the frontend origin. Step 17
    leaves the browser on the API's /docs page; clearing there silently emptied
    the wrong origin and the next login() then found itself already signed in.
    """
    if not page.url.startswith(BASE):
        page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.evaluate("() => { localStorage.clear(); }")


def select_row_with_status(page, status_label: str) -> None:
    """Open the first email in the list whose status badge reads ``status_label``."""
    row = page.locator("div.divide-y > button", has_text=status_label).first
    row.wait_for(timeout=15000)
    row.click()
    page.wait_for_timeout(1000)


def login(page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("#login-email", email)
    page.fill("#login-password", password)
    page.click("button:has-text('Sign In')")
    page.wait_for_url("**/dashboard", timeout=15000)
    page.wait_for_load_state("networkidle")


def run(page) -> None:
    # ---- 01 Login ---------------------------------------------------------
    page.goto(f"{BASE}/login", wait_until="networkidle")
    shot(page, "01-login", "Sign-in screen with role-based demo accounts")

    # ---- 02 Validation: rejected credentials ------------------------------
    page.fill("#login-email", "analyst@phishguard.local")
    page.fill("#login-password", "wrong-password")
    page.click("button:has-text('Sign In')")
    page.wait_for_selector("[role=alert]", timeout=15000)
    shot(page, "02-login-invalid-credentials",
         "Invalid credentials rejected with the API's own message (HTTP 401)")

    # ---- 03 Analyst dashboard --------------------------------------------
    login(page, *ANALYST)
    shot(page, "03-analyst-dashboard",
         "Analyst dashboard: live statistics, weekly threat distribution and risk mix")

    # ---- 04 Inbox, risk-sorted -------------------------------------------
    page.goto(f"{BASE}/inbox", wait_until="networkidle")
    shot(page, "04-analyst-inbox",
         "Email inbox sorted by risk score, with filter tabs and status badges")

    # ---- 05 Explainable detail -------------------------------------------
    page.click("button:has-text('High Risk')")
    page.wait_for_timeout(500)
    shot(page, "05-inbox-high-risk-filter", "Inbox filtered to high-risk messages only")

    rows = page.locator("div.divide-y > button")
    rows.first.click()
    page.wait_for_timeout(900)
    shot(page, "06-email-detail-explainable-score",
         "Email detail: risk score with the specific indicators that produced it, "
         "plus simulated SPF/DKIM/DMARC results")

    # ---- 07 Audit trail ---------------------------------------------------
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    shot(page, "07-audit-log",
         "Append-only audit trail recording actor, action, entity, detail and IP address")

    # ---- 08 Release-request queue (analyst view) --------------------------
    page.goto(f"{BASE}/release-requests", wait_until="networkidle")
    shot(page, "08-release-requests-analyst",
         "Release-request queue awaiting an analyst decision")

    # ---- 09 Staff portal --------------------------------------------------
    sign_out(page)
    login(page, *STAFF)
    page.goto(f"{BASE}/staff", wait_until="networkidle")
    shot(page, "09-staff-portal",
         "Staff portal showing only the signed-in user's own mail")

    # ---- 10 Client-side validation on the release request -----------------
    page.click("button:has-text('Request Email Release')")
    page.wait_for_selector("#release-reason", timeout=10000)
    page.fill("#release-reason", "too short")
    page.wait_for_timeout(400)
    shot(page, "10-release-request-validation",
         "Release request blocked until an adequate justification is supplied "
         "(mirrors the backend's 10-character rule)")

    # ---- 11 Valid reason accepted by the form, Submit now enabled ---------
    # The workflow figure's "submit a valid request" step needs the moment the form
    # accepts the justification, not the moment it refuses one. Captured before the
    # click so the enabled Submit button and the character counter are both visible.
    page.fill("#release-reason",
              "I was expecting this invoice from our supplier and I recognise the sender.")
    page.wait_for_timeout(400)
    shot(page, "11-release-request-valid-reason",
         "The same form with an adequate justification: the counter clears the "
         "10-character minimum and Submit Request becomes available")

    # ---- 12 Valid submission ---------------------------------------------
    page.click("button:has-text('Submit Request')")
    page.wait_for_timeout(1600)
    shot(page, "12-release-request-submitted",
         "Release request accepted and confirmed to the staff member")

    # ---- 13 Duplicate suppression ----------------------------------------
    page.click("button:has-text('Request Email Release')")
    page.wait_for_timeout(1000)
    shot(page, "13-duplicate-request-blocked",
         "A second request for the same email is refused (one open request per user)")

    # ---- 14 Analyst approves ---------------------------------------------
    sign_out(page)
    login(page, *ANALYST)
    page.goto(f"{BASE}/release-requests", wait_until="networkidle")
    approve = page.locator("button:has-text('Approve')").first
    approve.click()
    page.wait_for_timeout(1800)
    shot(page, "14-release-request-approved",
         "Analyst approval recorded; the underlying email is released in the same transaction")

    # ---- 14 Audit reflects the decision ----------------------------------
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    shot(page, "15-audit-after-approval",
         "Audit trail after the approval, showing release_request_approved")

    # ---- 15 Role-based access control ------------------------------------
    sign_out(page)
    login(page, *STAFF)
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    page.wait_for_timeout(900)
    shot(page, "16-staff-denied-audit-access",
         "Staff navigating to /audit is redirected to the dashboard; the API also "
         "returns 403 independently of the UI")

    # ---- 16 Error handling: backend unreachable --------------------------
    # Block API traffic at the browser so the UI's real failure path is exercised.
    page.route("**/api/**", lambda route: route.abort())
    page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
    page.wait_for_selector("[role=alert]", timeout=15000)
    shot(page, "17-error-state-api-unreachable",
         "Dashboard when the API cannot be reached: an explicit, retryable error "
         "instead of an empty or permanently loading screen")
    page.unroute("**/api/**")

    # ---- 17 API documentation --------------------------------------------
    page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
    page.wait_for_timeout(2000)
    shot(page, "18-openapi-docs",
         "Interactive OpenAPI documentation generated from the FastAPI application")

    # ---- 18 State machine: invalid analyst actions are not offered ---------
    # BUG-17 evidence. All three status-changing buttons used to be live on
    # every email; now the panel offers only the transitions the API accepts.
    sign_out(page)
    login(page, *ANALYST)
    page.goto(f"{BASE}/inbox", wait_until="networkidle")
    select_row_with_status(page, "Inbox")
    shot(page, "19-invalid-transition-blocked",
         "Delivered email selected: Release is disabled because the API accepts it "
         "only from quarantined or confirmed_phishing, while Quarantine and "
         "Confirm Phishing stay available")

    # ---- 19 The same rule in the staff view -------------------------------
    sign_out(page)
    login(page, *STAFF)
    page.goto(f"{BASE}/staff", wait_until="networkidle")
    select_row_with_status(page, "Inbox")
    shot(page, "20-release-request-not-applicable",
         "Staff view of a delivered email: the request button reads 'Already "
         "Delivered' and is disabled, because a release request applies only to "
         "email that is being held")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
        page = context.new_page()
        try:
            run(page)
        finally:
            context.close()
            browser.close()

    index = OUT / "INDEX.md"
    with open(index, "w", encoding="utf-8") as fh:
        fh.write("# Screenshot evidence\n\n")
        fh.write("Captured from the running application by "
                 "`evidence/capture_screenshots.py` (Playwright + Chromium, "
                 f"{VIEWPORT['width']}x{VIEWPORT['height']} at {SCALE}x). "
                 "No image is edited or mocked.\n\n")
        fh.write(f"Database engine serving these captures: **{engine()}**. The "
                 "script reads that from `/system/database-status` as it runs, so "
                 "the index cannot claim an engine the application was not using.\n\n")
        fh.write("| # | File | What it shows |\n|---|---|---|\n")
        for i, (name, desc) in enumerate(shots, 1):
            fh.write(f"| {i:02d} | `{name}` | {desc} |\n")
    print(f"\n{len(shots)} screenshots written to {OUT}")
    print(f"Index written to {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
