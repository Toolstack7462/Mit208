"""Convert the recorded .webm walkthrough to H.264 MP4.

Moodle and PowerPoint handle MP4/H.264 more reliably than VP8 WebM, so the
submitted file should be MP4.

ffmpeg lookup order:
  1. ffmpeg on PATH (a normal install)
  2. the copy Playwright ships for its own video encoding

Usage:
    python evidence/convert_video.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "video" / "PhishGuard_Walkthrough_raw.webm"
DST = HERE / "video" / "PhishGuard_Walkthrough.mp4"


def _has_h264(ffmpeg: str) -> bool:
    """Playwright ships a cut-down ffmpeg that can only encode VP8, so the
    presence of a binary is not enough — it has to have an H.264 encoder."""
    try:
        out = subprocess.run([ffmpeg, "-encoders"], capture_output=True,
                             text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "libx264" in out


def find_ffmpeg() -> str | None:
    """Return a path to an ffmpeg that can encode H.264, or None."""
    candidates: list[str] = []

    on_path = shutil.which("ffmpeg")
    if on_path:
        candidates.append(on_path)

    # imageio-ffmpeg ships a full build; pip install imageio-ffmpeg
    try:
        import imageio_ffmpeg
        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass

    # Playwright's own copy — last resort, and usually VP8-only.
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
        Path.home() / ".cache" / "ms-playwright",
        Path.home() / "Library" / "Caches" / "ms-playwright",
    ]
    for root in roots:
        if root.is_dir():
            for pattern in ("ffmpeg-*/ffmpeg-win64.exe", "ffmpeg-*/ffmpeg-*"):
                candidates += [str(c) for c in sorted(root.glob(pattern)) if c.is_file()]

    for candidate in candidates:
        if _has_h264(candidate):
            return candidate
    return None


def main() -> int:
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        print("Run 'python evidence/record_walkthrough.py' first.")
        return 1

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("No ffmpeg with an H.264 encoder was found.")
        print(f"The WebM recording is still usable at:\n  {SRC}")
        print("Get one with either:")
        print("  pip install imageio-ffmpeg          (simplest)")
        print("  https://ffmpeg.org/download.html    (full install)")
        return 2

    print(f"Using ffmpeg: {ffmpeg}")
    cmd = [
        ffmpeg, "-y", "-i", str(SRC),
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "23",
        # yuv420p + even dimensions keep the file playable in PowerPoint,
        # QuickTime and browsers.
        "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-movflags", "+faststart",
        "-an",                      # silent: narration is added by the student
        str(DST),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg failed:")
        print(result.stderr[-2500:])
        return result.returncode

    size_mb = DST.stat().st_size / 1_048_576
    print(f"\nMP4 written: {DST}  ({size_mb:.1f} MB)")
    print("The track is intentionally silent — record narration over it using "
          "evidence/NARRATION_SCRIPT.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
