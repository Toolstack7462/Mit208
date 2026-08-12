"""Make a saved PPTX report zero notes, and drop the now-unused notes master.

Removing the notes slides through python-pptx leaves two traces behind:

  docProps/app.xml           still reports the original <Notes> count, so a marker
                             checking document properties sees "Notes: 10" on a deck
                             that has none.
  ppt/notesMasters/          the master the notes slides referenced survives, along
                             with its relationship from presentation.xml.

Both are corrected here rather than in python-pptx, because the notes master is
referenced from presentation.xml and the relationship has to go at the same time or
PowerPoint reports the file as needing repair.

The notes master is removed only if no notesSlide part remains. If any does, the
master is left alone — a deck with notes needs it.

Usage:
    python evidence/strip_pptx_notes.py <file.pptx>
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

A = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"


def finalise_notes_metadata(path: Path) -> list[str]:
    """Zero the Notes count and drop the unused notes master. Returns a log."""
    notes: list[str] = []
    src = zipfile.ZipFile(path)
    names = src.namelist()

    remaining = [n for n in names if "notesSlide" in n]
    drop_master = not remaining
    doomed = set()
    if drop_master:
        doomed = {n for n in names if "notesMaster" in n}

    tmp = path.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            if item.filename in doomed:
                continue
            data = src.read(item.filename)

            if item.filename == "docProps/app.xml":
                text = data.decode("utf-8")
                before = re.search(r"<Notes>(\d+)</Notes>", text)
                text = re.sub(r"<Notes>\d+</Notes>", "<Notes>0</Notes>", text)
                data = text.encode("utf-8")
                notes.append(f"docProps/app.xml Notes: "
                             f"{before.group(1) if before else 'absent'} -> 0")

            elif item.filename == "ppt/presentation.xml" and drop_master:
                text = data.decode("utf-8")
                text = re.sub(r"<p:notesMasterIdLst>.*?</p:notesMasterIdLst>", "",
                              text, flags=re.S)
                data = text.encode("utf-8")

            elif item.filename == "ppt/_rels/presentation.xml.rels" and drop_master:
                text = data.decode("utf-8")
                text = re.sub(r'<Relationship[^>]*notesMaster[^>]*/>', "", text)
                data = text.encode("utf-8")

            elif item.filename == "[Content_Types].xml" and drop_master:
                text = data.decode("utf-8")
                text = re.sub(r'<Override[^>]*notesMaster[^>]*/>', "", text)
                data = text.encode("utf-8")

            out.writestr(item, data)
    src.close()
    shutil.move(str(tmp), str(path))

    if drop_master:
        notes.append(f"notes master removed ({len(doomed)} parts) — no notes slides remain")
    else:
        notes.append(f"notes master kept — {len(remaining)} notesSlide part(s) still present")
    return notes


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    for line in finalise_notes_metadata(Path(sys.argv[1])):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
