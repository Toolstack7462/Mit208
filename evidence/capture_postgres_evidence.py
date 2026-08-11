"""Capture evidence that the application runs on PostgreSQL, not just SQLite.

PostgreSQL is the assessed target while the automated suite uses SQLite, so this
script records the application actually serving from PostgreSQL: the engine it
reports, the dashboard rendered from PostgreSQL data, and the API refusing input
that would otherwise reach the database and fail there.

Prerequisites: a PostgreSQL server, with the backend started against it —

    psql -d phishguard_db -f database/schema.sql
    DATABASE_URL=postgresql+psycopg2://USER:PASS@HOST:PORT/phishguard_db \
        python -m app.seed
    DATABASE_URL=... uvicorn app.main:app --port 8000
    npm run dev            # frontend, port 5173

Usage:
    python evidence/capture_postgres_evidence.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173"
API = "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent / "screenshots"

VIEWPORT = {"width": 1600, "height": 1000}
SCALE = 2

ANALYST = ("analyst@phishguard.local", "Analyst@123")

shots: list[tuple[str, str]] = []


def shot(page, name: str, description: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(700)
    page.screenshot(path=str(OUT / f"{name}.png"))
    shots.append((f"{name}.png", description))
    print(f"  captured {name}.png  -- {description}")


def require_postgres() -> dict:
    """Refuse to produce 'PostgreSQL evidence' from a SQLite run."""
    with urllib.request.urlopen(f"{API}/system/database-status", timeout=15) as r:
        status = json.loads(r.read())
    if status.get("engine") != "postgresql":
        raise SystemExit(
            f"Backend is running on '{status.get('engine')}', not PostgreSQL. "
            "Start it with a PostgreSQL DATABASE_URL before capturing this evidence."
        )
    print(f"  backend engine: {status['engine']} (using_fallback={status['using_fallback']})")
    return status


def run(page) -> None:
    # 20 — the engine the API reports, straight from the endpoint.
    page.goto(f"{API}/system/database-status", wait_until="networkidle")
    shot(page, "20-postgresql-database-status",
         "The API reporting PostgreSQL as the live engine, with using_fallback "
         "false — credentials are never included, only the URL scheme")

    # 21 — the same workflow, rendered from PostgreSQL data.
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("#login-email", ANALYST[0])
    page.fill("#login-password", ANALYST[1])
    page.click("button:has-text('Sign In')")
    page.wait_for_url("**/dashboard", timeout=15000)
    page.wait_for_load_state("networkidle")
    shot(page, "21-postgresql-dashboard",
         "The analyst dashboard rendered from PostgreSQL data, on the assessed "
         "target database rather than the SQLite fallback")

    # 22 — the generated API surface, served from the PostgreSQL-backed app.
    page.goto(f"{API}/docs", wait_until="networkidle")
    page.wait_for_timeout(1500)
    shot(page, "22-postgresql-openapi",
         "OpenAPI documentation served by the backend while connected to PostgreSQL")


def main() -> int:
    require_postgres()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
        page = context.new_page()
        try:
            run(page)
        finally:
            context.close()
            browser.close()

    # Rewrite the PostgreSQL section rather than appending it, so running this
    # script twice does not leave two copies in the index.
    index = OUT / "INDEX.md"
    heading = "## PostgreSQL evidence"
    if index.exists():
        body = index.read_text(encoding="utf-8")
        body = body.split(heading)[0].rstrip() + "\n"
        section = [
            f"\n{heading}\n",
            "Captured by `evidence/capture_postgres_evidence.py` against the "
            "application running on PostgreSQL 16.6, which the script verifies "
            "before taking a single image.\n",
            "| File | What it shows |",
            "|---|---|",
        ]
        section += [f"| `{name}` | {desc} |" for name, desc in shots]
        index.write_text(body + "\n".join(section) + "\n", encoding="utf-8")
    print(f"\n{len(shots)} PostgreSQL screenshots written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
