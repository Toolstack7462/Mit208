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
| `capture_screenshots.py` | Drives Chromium through the full workflow and writes 17 labelled screenshots |
| `screenshots/` | The 17 PNGs, at 3200 x 2000 |
| `screenshots/INDEX.md` | Generated table describing every image |
| `record_walkthrough.py` | Records a 4-minute screen capture of the same workflow |
| `convert_video.py` | Converts the recording to H.264 MP4 |
| `video/PhishGuard_Walkthrough.mp4` | The walkthrough, 4:00, 1280x720, **silent** |
| `video/PhishGuard_Walkthrough_raw.webm` | The original Playwright recording (VP8) |
| `video/TIMING.md` | Generated timeline of what appears when |
| `NARRATION_SCRIPT.md` | Draft narration and shot list for the student to record |
| `update_report.py`, `trim_report.py`, `trim_report2.py` | Edit the report DOCX in place: correct figures, then fit the word allocation |
| `update_pptx.py` | Edits the presentation in place: figures, screenshots, speaker notes |

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

**PostgreSQL.** The captures were taken against the SQLite fallback, which
`/system/database-status` states plainly in screenshot 17 and in the recording.
PostgreSQL is verified by the `backend-postgres` job in
`.github/workflows/ci.yml`, which applies `database/schema.sql` to a real
PostgreSQL 16 service and checks the seed. Capturing the same workflow against a
local PostgreSQL instance remains a manual step —
see `docs/SUBMISSION_CHECKLIST.md`.

---

## Privacy

Nothing captured here exposes real data. The demo accounts use the reserved,
non-routable `.local` domain; every sample message is synthetic; the look-alike
domains (`paypa1-support.com`, `micros0ft-alerts.com`) are deliberately
misspelled so no real company domain appears; and no screen shows a secret key or
a database credential. The passwords visible on the sign-in screen are the
documented test credentials the assessment asks for.
