"""Render the PhishGuard data model as a labelled PNG for the report.

The canonical data model is `docs/ERD.md` (Mermaid) and `database/schema.sql`
(DDL). Mermaid needs a browser or the Mermaid CLI to rasterise, and the report
needs a figure that stays readable at 100% zoom in the PDF, so this script draws
the same five tables directly at 2600x1560 with no external service.

The column lists below are transcribed from `backend/app/models.py`; the
`verify_matches_models()` check at the bottom fails the script if a table or
column name has been renamed since, so the figure cannot quietly go stale.

Usage:
    python evidence/make_erd_figure.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / "figures" / "erd-data-model.png"

W, H = 2600, 1560
BG = (255, 255, 255)
NAVY = (15, 23, 42)
HEAD_BG = (30, 41, 59)
BRAND = (37, 99, 235)
LINE = (100, 116, 139)
BORDER = (203, 213, 225)
ROW_ALT = (248, 250, 252)
TEXT = (30, 41, 59)
MUTED = (100, 116, 139)
KEYCOL = (37, 99, 235)

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"),
             Path("/System/Library/Fonts")]
BOLD_NAMES = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc"]
REG_NAMES = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"]
MONO_NAMES = ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"]


def _font(names: list[str], size: int) -> ImageFont.FreeTypeFont:
    for d in FONT_DIRS:
        for n in names:
            p = d / n
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    continue
    return ImageFont.load_default()


F_TITLE = _font(BOLD_NAMES, 44)
F_SUB = _font(REG_NAMES, 27)
F_TBL = _font(BOLD_NAMES, 30)
F_COL = _font(MONO_NAMES, 24)
F_NOTE = _font(REG_NAMES, 23)
F_REL = _font(BOLD_NAMES, 23)

# (table, x, y, width, [(column, type, key)])  key: "PK" | "FK" | "UK" | ""
TABLES = [
    ("users", 70, 250, 620, [
        ("id", "int", "PK"),
        ("email", "varchar(255)", "UK"),
        ("full_name", "varchar(255)", ""),
        ("hashed_password", "varchar(255)", ""),
        ("role", "varchar(32)", ""),
        ("is_active", "boolean", ""),
        ("created_at", "timestamptz", ""),
    ]),
    ("email_records", 1910, 250, 620, [
        ("id", "int", "PK"),
        ("message_id", "varchar(255)", "UK"),
        ("sender", "varchar(320)", ""),
        ("recipient", "varchar(320)", ""),
        ("subject", "varchar(500)", ""),
        ("body", "text", ""),
        ("status", "varchar(32)", ""),
        ("risk_score", "int 0-100", ""),
        ("risk_level", "varchar(16)", ""),
        ("score_reasons", "text (JSON)", ""),
        ("auth_spf/dkim/dmarc", "varchar(8)", ""),
        ("templated_language", "boolean", ""),
        ("received_at", "timestamptz", ""),
    ]),
    ("analyst_reviews", 990, 250, 620, [
        ("id", "int", "PK"),
        ("email_id", "int", "FK"),
        ("analyst_id", "int", "FK"),
        ("action", "varchar(32)", ""),
        ("verdict", "varchar(32)", ""),
        ("feedback", "text", ""),
        ("created_at", "timestamptz", ""),
    ]),
    ("staff_release_requests", 990, 700, 620, [
        ("id", "int", "PK"),
        ("email_id", "int", "FK"),
        ("requested_by", "int", "FK"),
        ("reason", "text (>= 10 ch)", ""),
        ("status", "varchar(16)", ""),
        ("reviewed_by", "int null", "FK"),
        ("review_note", "text", ""),
        ("created_at", "timestamptz", ""),
        ("reviewed_at", "timestamptz null", ""),
    ]),
    ("audit_logs", 70, 1030, 620, [
        ("id", "int", "PK"),
        ("user_id", "int null", "FK"),
        ("actor_email", "varchar(255)", ""),
        ("action", "varchar(64)", ""),
        ("entity_type", "varchar(64)", ""),
        ("entity_id", "int", ""),
        ("details", "text", ""),
        ("ip_address", "varchar(64)", ""),
        ("created_at", "timestamptz", ""),
    ]),
]

HEAD_H = 58
ROW_H = 40
PAD = 16

boxes: dict[str, tuple[int, int, int, int]] = {}


def draw_table(d: ImageDraw.ImageDraw, name, x, y, w, cols) -> None:
    h = HEAD_H + ROW_H * len(cols)
    boxes[name] = (x, y, x + w, y + h)

    d.rectangle([x + 5, y + 6, x + w + 5, y + h + 6], fill=(226, 232, 240))
    d.rectangle([x, y, x + w, y + h], fill=(255, 255, 255), outline=BORDER, width=2)
    d.rectangle([x, y, x + w, y + HEAD_H], fill=HEAD_BG)
    d.text((x + PAD, y + HEAD_H // 2), name, font=F_TBL, fill=(255, 255, 255), anchor="lm")

    for i, (col, typ, key) in enumerate(cols):
        ry = y + HEAD_H + i * ROW_H
        if i % 2 == 1:
            d.rectangle([x + 2, ry, x + w - 2, ry + ROW_H], fill=ROW_ALT)
        label = f"{key} " if key else ""
        cx = x + PAD
        if label:
            d.text((cx, ry + ROW_H // 2), label.strip(), font=F_COL, fill=KEYCOL, anchor="lm")
            cx += 54
        d.text((cx, ry + ROW_H // 2), col, font=F_COL, fill=TEXT, anchor="lm")
        d.text((x + w - PAD, ry + ROW_H // 2), typ, font=F_COL, fill=MUTED, anchor="rm")


def crow(d: ImageDraw.ImageDraw, x: int, y: int, facing: str) -> None:
    """Draw a crow's-foot (many) marker pointing away from the entity."""
    s = 15
    dx = -1 if facing == "left" else 1
    for off in (-s, 0, s):
        d.line([(x, y), (x + dx * 26, y + off)], fill=LINE, width=4)


def one(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    d.line([(x, y - 15), (x, y + 15)], fill=LINE, width=5)


def relate(d, a, b, label, *, a_side="right", b_side="left", via=None):
    ax1, ay1, ax2, ay2 = boxes[a]
    bx1, by1, bx2, by2 = boxes[b]
    sx = ax2 if a_side == "right" else ax1
    sy = (ay1 + ay2) // 2
    ex = bx1 if b_side == "left" else bx2
    ey = (by1 + by2) // 2
    if via is None:
        via = (sx + ex) // 2
    pts = [(sx, sy), (via, sy), (via, ey), (ex, ey)]
    d.line(pts, fill=LINE, width=4, joint="curve")
    one(d, sx + (8 if a_side == "right" else -8), sy)
    crow(d, ex + (-8 if b_side == "left" else 8), ey, "left" if b_side == "left" else "right")
    tw = d.textlength(label, font=F_REL)
    ly = (sy + ey) // 2
    d.rectangle([via - tw / 2 - 12, ly - 20, via + tw / 2 + 12, ly + 20], fill=BG)
    d.text((via, ly), label, font=F_REL, fill=BRAND, anchor="mm")


def main() -> int:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.text((W // 2, 70), "PhishGuard data model", font=F_TITLE, fill=NAVY, anchor="mm")
    d.text((W // 2, 128),
           "Five tables. PK = primary key, FK = foreign key, UK = unique. "
           "One-to-many shown as | ---< ",
           font=F_SUB, fill=MUTED, anchor="mm")
    d.line([(70, 176), (W - 70, 176)], fill=BORDER, width=3)

    for name, x, y, w, cols in TABLES:
        draw_table(d, name, x, y, w, cols)

    # users 1---< analyst_reviews.analyst_id
    relate(d, "users", "analyst_reviews", "performs", via=840)
    # email_records 1---< analyst_reviews.email_id
    relate(d, "email_records", "analyst_reviews", "is reviewed by",
           a_side="left", b_side="right", via=1760)
    # users 1---< staff_release_requests (requested_by + reviewed_by)
    relate(d, "users", "staff_release_requests", "raises / reviews", via=880)
    # email_records 1---< staff_release_requests
    relate(d, "email_records", "staff_release_requests", "is subject of",
           a_side="left", b_side="right", via=1720)
    # users 1---< audit_logs  (straight down the left column)
    ux1, uy1, ux2, uy2 = boxes["users"]
    ax1, ay1, ax2, ay2 = boxes["audit_logs"]
    d.line([(ux1 + 130, uy2), (ux1 + 130, ay1)], fill=LINE, width=4)
    one(d, ux1 + 130, uy2 + 10)
    d.line([(ux1 + 130, ay1 - 8), (ux1 + 104, ay1 - 34)], fill=LINE, width=4)
    d.line([(ux1 + 130, ay1 - 8), (ux1 + 130, ay1 - 40)], fill=LINE, width=4)
    d.line([(ux1 + 130, ay1 - 8), (ux1 + 156, ay1 - 34)], fill=LINE, width=4)
    lbl = "is actor of"
    tw = d.textlength(lbl, font=F_REL)
    my = (uy2 + ay1) // 2
    d.rectangle([ux1 + 130 - tw / 2 - 12, my - 20, ux1 + 130 + tw / 2 + 12, my + 20], fill=BG)
    d.text((ux1 + 130, my), lbl, font=F_REL, fill=BRAND, anchor="mm")

    # Integrity notes
    notes = [
        ("Integrity rules enforced by the database", True),
        ("CHECK on users.role, email_records.status,", False),
        ("risk_level, auth_spf/dkim/dmarc, and", False),
        ("risk_score BETWEEN 0 AND 100.", False),
        ("CHECK that a decided release request names", False),
        ("its reviewer, and a pending one does not.", False),
        ("", False),
        ("PARTIAL UNIQUE INDEX", True),
        ("uq_request_one_pending_per_email_user", False),
        ("ON (email_id, requested_by)", False),
        ("WHERE status = 'pending'", False),
        ("makes one open request per user per email", False),
        ("atomic, not just checked in the API.", False),
        ("", False),
        ("Reviews and requests cascade when an email", False),
        ("row is deleted. audit_logs is append-only at", False),
        ("the application level: no route updates or", False),
        ("deletes a row.", False),
    ]
    nx, ny, nw = 1910, 1000, 620
    d.rectangle([nx, ny, nx + nw, ny + 25 * len(notes) + 36], fill=ROW_ALT,
                outline=BORDER, width=2)
    for i, (line, strong) in enumerate(notes):
        d.text((nx + 20, ny + 24 + i * 25), line,
               font=F_REL if strong else F_NOTE,
               fill=BRAND if strong else TEXT, anchor="lm")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")
    print(f"ERD figure written: {OUT}  ({img.width}x{img.height})")
    return 0


def verify_matches_models() -> None:
    """Fail loudly if a table or column drawn here no longer exists in the ORM."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    try:
        from app.models import Base
    except Exception as exc:  # pragma: no cover - only when run outside the repo
        print(f"  (skipped ORM cross-check: {exc})")
        return
    real = {t.name: {c.name for c in t.columns} for t in Base.metadata.sorted_tables}
    problems = []
    for name, _, _, _, cols in TABLES:
        if name not in real:
            problems.append(f"table '{name}' is not in the ORM")
            continue
        for col, _, _ in cols:
            for part in col.replace("auth_spf/dkim/dmarc", "auth_spf").split("/"):
                if part not in real[name]:
                    problems.append(f"{name}.{part} is not in the ORM")
    if problems:
        raise SystemExit("ERD figure is stale:\n  " + "\n  ".join(problems))
    print("  ORM cross-check passed: every table and column drawn still exists.")


if __name__ == "__main__":
    rc = main()
    verify_matches_models()
    sys.exit(rc)
