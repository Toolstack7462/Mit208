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

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
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


def sign_out(page) -> None:
    """Clear the stored session so the next login starts clean."""
    page.evaluate("() => { localStorage.clear(); }")


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

    # ---- 11 Valid submission ---------------------------------------------
    page.fill("#release-reason",
              "I was expecting this invoice from our supplier and I recognise the sender.")
    page.wait_for_timeout(300)
    page.click("button:has-text('Submit Request')")
    page.wait_for_timeout(1600)
    shot(page, "11-release-request-submitted",
         "Release request accepted and confirmed to the staff member")

    # ---- 12 Duplicate suppression ----------------------------------------
    page.click("button:has-text('Request Email Release')")
    page.wait_for_timeout(1000)
    shot(page, "12-duplicate-request-blocked",
         "A second request for the same email is refused (one open request per user)")

    # ---- 13 Analyst approves ---------------------------------------------
    sign_out(page)
    login(page, *ANALYST)
    page.goto(f"{BASE}/release-requests", wait_until="networkidle")
    approve = page.locator("button:has-text('Approve')").first
    approve.click()
    page.wait_for_timeout(1800)
    shot(page, "13-release-request-approved",
         "Analyst approval recorded; the underlying email is released in the same transaction")

    # ---- 14 Audit reflects the decision ----------------------------------
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    shot(page, "14-audit-after-approval",
         "Audit trail after the approval, showing release_request_approved")

    # ---- 15 Role-based access control ------------------------------------
    sign_out(page)
    login(page, *STAFF)
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    page.wait_for_timeout(900)
    shot(page, "15-staff-denied-audit-access",
         "Staff navigating to /audit is redirected to the dashboard; the API also "
         "returns 403 independently of the UI")

    # ---- 16 Error handling: backend unreachable --------------------------
    # Block API traffic at the browser so the UI's real failure path is exercised.
    page.route("**/api/**", lambda route: route.abort())
    page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
    page.wait_for_selector("[role=alert]", timeout=15000)
    shot(page, "16-error-state-api-unreachable",
         "Dashboard when the API cannot be reached: an explicit, retryable error "
         "instead of an empty or permanently loading screen")
    page.unroute("**/api/**")

    # ---- 17 API documentation --------------------------------------------
    page.goto("http://127.0.0.1:8000/docs", wait_until="networkidle")
    page.wait_for_timeout(2000)
    shot(page, "17-openapi-docs",
         "Interactive OpenAPI documentation generated from the FastAPI application")


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
        fh.write("| # | File | What it shows |\n|---|---|---|\n")
        for i, (name, desc) in enumerate(shots, 1):
            fh.write(f"| {i:02d} | `{name}` | {desc} |\n")
    print(f"\n{len(shots)} screenshots written to {OUT}")
    print(f"Index written to {index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
