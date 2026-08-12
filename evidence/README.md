# Evidence

Everything in this folder was produced by running the scripts here against the
**real** PhishGuard application. No image is edited, drawn or mocked, and no
result is transcribed by hand — each script writes its own index or timeline as
it runs, so the evidence and the description of it cannot drift apart.

Re-run the scripts after any interface change and the evidence updates itself.

---

## Contents

| Path | What it is |
|---|---|
| `capture_screenshots.py` | Drives Chromium through the full workflow and writes 19 labelled screenshots, recording which database engine served them |
| `capture_postgres_evidence.py` | Three captures proving the app runs on PostgreSQL; refuses to run on any other engine |
| `capture_ci_evidence.py` | The passing CI run and the release tag, plus `ci_evidence.json` for the report; refuses to run unless CI passed |
| `screenshots/` | The 24 PNGs (19 workflow + 3 PostgreSQL + 2 CI/release), at 3200 x 2000 |
| `screenshots/INDEX.md` | Generated table describing every image |
| `index_section.py` | Lets the capture scripts each own one section of that index without clobbering the others |
| `secret_scan.py` | Scans every tracked file for committed credentials; also a CI job |
| `make_architecture_figure.py` | The layered architecture drawing, in report and projector variants |
| `make_erd_figure.py` | The data-model figure |
| `make_workflow_figure.py` | The four-pane core-workflow figure, laid out for legibility at print size |
| `figures/` | The four generated figures used by the report and the deck |
| `record_walkthrough.py` | Records a 4-minute screen capture of the same workflow |
| `convert_video.py` | Converts the recording to H.264 MP4 |
| `video/PhishGuard_Walkthrough.mp4` | The walkthrough, 3:58, 1280x720, **silent** |
| `video/PhishGuard_Walkthrough_raw.webm` | The original Playwright recording (VP8) |
| `video/TIMING.md` | Generated timeline of what appears when |
| `NARRATION_SCRIPT.md` | Draft narration and shot list for the student to record |
| `update_report.py`, `trim_report.py`, `trim_report2.py` | Earlier passes over the report DOCX: correct figures, then fit the word allocation |
| `finalise_report.py` | The final pass: removes placeholders, adds the figures and appendices, removes the blank pages the section breaks leave behind, and reports the word count the way the brief counts it |
| `update_pptx.py`, `finalise_pptx.py` | Edit the presentation in place: figures and screenshots. Every substitution is checked, so a stale figure cannot survive silently. The presenter prompts are exported to the private rehearsal set and then removed from the submitted deck |
| `to_pdf.ps1` | Renders the DOCX and PPTX to PDF with Word and PowerPoint, so the pagination matches what the author saw |

---

## Prerequisites

```bash
pip install playwright python-docx python-pptx pillow
playwright install chromium

# For MP4 conversion. Playwright bundles an ffmpeg that can only encode VP8,
# so a build with an H.264 encoder is needed:
pip install imageio-ffmpeg
```

## Reproducing the evidence

Start the application first — the scripts drive the real thing, so if it is not
running they will fail rather than invent a result.

```bash
# Terminal 1 — backend on a freshly seeded database
cd backend
python -m app.seed --reset
uvicorn app.main:app --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev

# Terminal 3 — capture
python evidence/capture_screenshots.py     # -> evidence/screenshots/ + INDEX.md
python evidence/record_walkthrough.py      # -> evidence/video/*.webm + TIMING.md
python evidence/convert_video.py           # -> evidence/video/*.mp4
```

Re-seed between the screenshot run and the recording run. Both scripts perform
real actions — they approve a release request, for instance — so a second run
against the same database starts from a different state.

---

## What the recording deliberately does not contain

**Audio.** The MP4 has no sound track. The narration must be the author's own
voice, so `NARRATION_SCRIPT.md` supplies a draft to read, adapt or discard rather
than a synthesised voice-over. Anything in that script the author could not
defend in the live showcase should be cut.

That is the only deliberate omission.

---

## Which database the captures were taken against

As of **12 August 2026** the whole set was captured against the application
running on **PostgreSQL 16.6**, not the SQLite fallback. Screenshot 21 is the
`/system/database-status` response showing `"engine":"postgresql"` and
`"using_fallback":false`; `capture_postgres_evidence.py` refuses to run at all if
the backend reports any other engine.

The `backend-postgres` job in `.github/workflows/ci.yml` repeats the same
verification on every push — it applies `database/schema.sql` to a real
PostgreSQL 16 service, seeds into it, checks the constraints reject invalid SQL,
and runs the whole test suite against it.

---

## Privacy

Nothing captured here exposes real data. The demo accounts use the reserved,
non-routable `.local` domain; every sample message is synthetic; the look-alike
domains (`paypa1-support.com`, `micros0ft-alerts.com`) are deliberately
misspelled so no real company domain appears; and no screen shows a secret key or
a database credential. The passwords visible on the sign-in screen are the
documented test credentials the assessment asks for.
