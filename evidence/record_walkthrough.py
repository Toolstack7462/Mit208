"""Record a 3-4 minute screen capture of the REAL running PhishGuard application.

Produces a silent video of the genuine application, paced to the timing the
assessment brief asks for. The student records or approves the narration
separately, using evidence/NARRATION_SCRIPT.md.

Nothing here is staged: every screen is the running app responding to real
requests against the seeded database.

Prerequisites (see README):
    backend :  python -m app.seed --reset  &&  uvicorn app.main:app --port 8000
    frontend:  npm run dev                                  (port 5173)
    tooling :  pip install playwright  &&  playwright install chromium

Usage:
    python evidence/record_walkthrough.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
API = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent / "video"

# 1280x720 keeps the file a sensible size for a Moodle upload while staying
# readable; Playwright records at the viewport size.
VIEWPORT = {"width": 1280, "height": 720}

ANALYST = ("analyst@phishguard.local", "Analyst@123")
STAFF = ("staff@phishguard.local", "Staff@123")

# Segment boundaries from the assessment brief, used to keep the recording on
# schedule. (label, target end time in seconds)
#
# The brief allows three to four minutes. The final target is 236 rather than 240
# because the encoder flushes a short tail after the last frame: a run paced to
# exactly 240 produced a 240.12-second file, which is over the limit even though
# Windows rounds it to 4:00 and hides the overrun.
SEGMENTS = [
    ("Problem and final MVP", 30),
    ("Architecture and components", 75),
    ("Main working user flow", 140),
    ("Packages, a decision and a bug fixed", 188),
    ("Testing, limitations, repository", 236),
]

started = 0.0
marks: list[tuple[str, float]] = []


def elapsed() -> float:
    return time.monotonic() - started


def mark(label: str) -> None:
    marks.append((label, elapsed()))
    print(f"  [{elapsed():6.1f}s] {label}")


def hold(seconds: float) -> None:
    """Dwell so a viewer (and the narrator) can actually read the screen."""
    time.sleep(seconds)


def pace_to(target: float) -> None:
    """Wait until the segment's scheduled end, if we arrived early."""
    remaining = target - elapsed()
    if remaining > 0:
        time.sleep(remaining)


def login(page, email: str, password: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    hold(1.0)
    page.fill("#login-email", email)
    hold(0.4)
    page.fill("#login-password", password)
    hold(0.6)
    page.click("button:has-text('Sign In')")
    page.wait_for_url("**/dashboard", timeout=15000)
    page.wait_for_load_state("networkidle")


def sign_out(page) -> None:
    page.evaluate("() => { localStorage.clear(); }")


def run(page) -> None:
    # ================= 0:00-0:30  Problem and final MVP ====================
    mark("Segment 1: login screen — problem and MVP framing")
    page.goto(f"{BASE}/login", wait_until="networkidle")
    hold(6)

    # A rejected sign-in, up front, shows validation is real.
    page.fill("#login-email", "analyst@phishguard.local")
    page.fill("#login-password", "wrong-password")
    page.click("button:has-text('Sign In')")
    page.wait_for_selector("[role=alert]", timeout=15000)
    hold(5)
    pace_to(SEGMENTS[0][1])

    # ================= 0:30-1:15  Architecture ==============================
    mark("Segment 2: OpenAPI docs — the backend contract")
    page.goto(f"{API}/docs", wait_until="networkidle")
    hold(4)
    # Scroll slowly through the endpoint groups so each is legible.
    for _ in range(5):
        page.mouse.wheel(0, 320)
        hold(1.6)
    hold(3)

    mark("Segment 2: live database-status endpoint")
    page.goto(f"{API}/system/database-status", wait_until="networkidle")
    hold(5)
    page.goto(f"{API}/health", wait_until="networkidle")
    hold(4)
    pace_to(SEGMENTS[1][1])

    # ================= 1:15-2:20  Main working user flow ====================
    mark("Segment 3: analyst dashboard")
    login(page, *ANALYST)
    hold(7)

    mark("Segment 3: risk-sorted inbox")
    page.goto(f"{BASE}/inbox", wait_until="networkidle")
    hold(5)
    page.click("button:has-text('High Risk')")
    hold(4)

    mark("Segment 3: explainable score on the worst message")
    rows = page.locator("div.divide-y > button")
    rows.first.click()
    hold(9)
    # Scroll the detail panel to reveal the message body under the indicators.
    page.mouse.move(900, 500)
    for _ in range(3):
        page.mouse.wheel(0, 260)
        hold(1.5)
    hold(2)

    mark("Segment 3: staff sees only their own mail, and requests a release")
    sign_out(page)
    login(page, *STAFF)
    page.goto(f"{BASE}/staff", wait_until="networkidle")
    hold(6)
    page.click("button:has-text('Request Email Release')")
    page.wait_for_selector("#release-reason", timeout=10000)
    hold(2)
    # Show the justification rule refusing an inadequate reason first.
    page.fill("#release-reason", "please")
    hold(4)
    page.fill("#release-reason",
              "I was expecting this invoice from our supplier and I recognise the sender.")
    hold(3)
    page.click("button:has-text('Submit Request')")
    hold(5)
    pace_to(SEGMENTS[2][1])

    # ========= 2:20-3:10  Packages, a decision, and a bug fixed ============
    mark("Segment 4: duplicate request refused (the defect that was fixed)")
    page.click("button:has-text('Request Email Release')")
    hold(6)

    mark("Segment 4: analyst decides the request")
    sign_out(page)
    login(page, *ANALYST)
    page.goto(f"{BASE}/release-requests", wait_until="networkidle")
    hold(6)
    page.locator("button:has-text('Approve')").first.click()
    hold(6)

    mark("Segment 4: the approval released the email in one transaction")
    page.goto(f"{BASE}/inbox", wait_until="networkidle")
    hold(5)
    pace_to(SEGMENTS[3][1])

    # ============ 3:10-4:00  Testing, limitations, repository ==============
    mark("Segment 5: audit trail")
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    hold(9)
    page.mouse.wheel(0, 400)
    hold(4)

    mark("Segment 5: role-based access control enforced")
    sign_out(page)
    login(page, *STAFF)
    page.goto(f"{BASE}/audit", wait_until="networkidle")
    hold(6)

    mark("Segment 5: error handling when the API is unreachable")
    page.route("**/api/**", lambda route: route.abort())
    page.goto(f"{BASE}/dashboard", wait_until="domcontentloaded")
    page.wait_for_selector("[role=alert]", timeout=15000)
    hold(8)
    page.unroute("**/api/**")
    pace_to(SEGMENTS[4][1])
    mark("Recording complete")


def main() -> int:
    global started
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(OUT),
            record_video_size=VIEWPORT,
        )
        page = context.new_page()
        started = time.monotonic()
        raw = None
        try:
            run(page)
        finally:
            total = elapsed()
            # Resolve the path BEFORE the context closes: once Playwright has
            # stopped, video.path() can no longer be called.
            if page.video:
                raw = Path(page.video.path())
            context.close()          # finalises the .webm file
            browser.close()

    print(f"\nRecorded {total:.1f}s ({total / 60:.1f} min)")
    if raw and raw.exists():
        target = OUT / "PhishGuard_Walkthrough_raw.webm"
        if target.exists():
            target.unlink()
        raw.rename(target)
        print(f"Video: {target}  ({target.stat().st_size / 1_048_576:.1f} MB)")
        print("Convert to MP4 with:  python evidence/convert_video.py")

    with open(OUT / "TIMING.md", "w", encoding="utf-8") as fh:
        fh.write("# Recording timeline\n\n")
        fh.write(f"Total duration: **{total:.0f} seconds ({total / 60:.1f} minutes)**\n\n")
        fh.write("Captured from the running application by "
                 "`evidence/record_walkthrough.py`.\n\n")
        fh.write("| Time | On screen |\n|---|---|\n")
        for label, at in marks:
            fh.write(f"| {int(at) // 60}:{int(at) % 60:02d} | {label} |\n")
    print(f"Timeline: {OUT / 'TIMING.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
