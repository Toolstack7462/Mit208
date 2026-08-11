"""Capture the continuous-integration and release evidence from the public repo.

Two things come out of one run, which is the point: the screenshots the report
reproduces, and a JSON record of the same facts that finalise_report.py reads.
Nothing about the CI run is typed into the report by hand, so the report cannot
quote a run number, commit or conclusion that has since moved on.

It refuses to write anything if the latest run did not pass, so "successful CI
evidence" cannot be produced from a failing build.

Usage:
    python evidence/capture_ci_evidence.py [tag]
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from index_section import write_section  # noqa: E402

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "screenshots"
OUT_JSON = HERE / "ci_evidence.json"

OWNER_REPO = "Toolstack7462/Mit208"
API = f"https://api.github.com/repos/{OWNER_REPO}"
REPO_URL = f"https://github.com/{OWNER_REPO}"

VIEWPORT = {"width": 1600, "height": 1000}
SCALE = 2

RUN_SHOT = "23-ci-run-passing.png"
TAG_SHOT = "24-release-tag.png"


def api(path: str):
    req = urllib.request.Request(f"{API}{path}",
                                 headers={"User-Agent": "phishguard-evidence",
                                          "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def latest_run() -> dict:
    runs = api("/actions/runs?per_page=1")["workflow_runs"]
    if not runs:
        raise SystemExit("no workflow runs found on the public repository")
    return runs[0]


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "v1.1-final"

    run = latest_run()
    if run["status"] != "completed" or run["conclusion"] != "success":
        raise SystemExit(
            f"the latest run (#{run['run_number']}, {run['head_sha'][:7]}) is "
            f"status={run['status']} conclusion={run['conclusion']}. This script "
            "will not produce 'successful CI evidence' from a run that did not pass."
        )

    jobs = api(f"/actions/runs/{run['id']}/jobs")["jobs"]
    record = {
        "run_number": run["run_number"],
        "run_id": run["id"],
        "run_url": run["html_url"],
        "sha": run["head_sha"],
        "conclusion": run["conclusion"],
        "created_at": run["created_at"],
        "jobs": [{"name": j["name"], "conclusion": j["conclusion"]} for j in jobs],
        "tag": tag,
        "tag_url": f"{REPO_URL}/releases/tag/{tag}",
        "run_shot": RUN_SHOT,
        "tag_shot": TAG_SHOT,
    }

    print(f"Run #{run['run_number']} on {run['head_sha'][:7]}: {run['conclusion']}")
    for j in record["jobs"]:
        print(f"  {j['conclusion']:<9} {j['name']}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=SCALE)
        page = context.new_page()
        try:
            page.goto(record["run_url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            page.screenshot(path=str(SHOTS / RUN_SHOT))
            print(f"  captured {RUN_SHOT}")

            page.goto(record["tag_url"], wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
            page.screenshot(path=str(SHOTS / TAG_SHOT))
            print(f"  captured {TAG_SHOT}")
        finally:
            context.close()
            browser.close()

    OUT_JSON.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nFacts written to {OUT_JSON}")

    # Replace this script's own section of the index in place.
    lines = [
        f"Captured by `evidence/capture_ci_evidence.py`, which reads the run from the "
        f"GitHub API and refuses to write anything unless it passed. Run "
        f"#{record['run_number']} on commit {record['sha'][:7]}, all "
        f"{len(record['jobs'])} jobs green.",
        "",
        "| File | What it shows |",
        "|---|---|",
        f"| `{RUN_SHOT}` | GitHub Actions run #{record['run_number']} on the public "
        f"repository, every job green |",
        f"| `{TAG_SHOT}` | The assessed version, tag {tag}, on the public repository |",
    ]
    if write_section(SHOTS / "INDEX.md",
                     "## Continuous integration and release evidence", lines):
        print("Index section written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
