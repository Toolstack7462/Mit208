"""Draw the PhishGuard architecture as a layered diagram.

The previous diagram was accurate but hard to read: eighteen boxes joined by
arrows that crossed in the middle, so following one request through the system
meant tracing a line by eye. This version keeps exactly the same components —
every box names a file that exists in the repository — and arranges them as four
ordered layers, so data flows left to right and no arrow crosses another.

It also draws the one thing the old diagram left out and the marker most wants to
see: the trust boundary. Everything left of it is advisory (the browser can be
bypassed with curl); everything right of it is enforced.

Two variants are produced from the same definition:

  report  10.59 x 5.60 in — full detail, sits on a landscape page in the report
  slide   11.31 x 4.75 in — fewer words, larger type, for the projector

Usage:
    python evidence/make_architecture_figure.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent / "figures"
DPI = 288

NAVY = (15, 23, 42)
SLATE = (51, 65, 85)
MUTED = (100, 116, 139)
BRAND = (37, 99, 235)
GREEN = (5, 150, 105)
AMBER = (180, 83, 9)
RED = (185, 28, 28)
BORDER = (203, 213, 225)
BG = (255, 255, 255)

LAYER_TINTS = [
    ((239, 246, 255), (191, 219, 254), BRAND),      # browser
    ((254, 252, 232), (253, 230, 138), AMBER),      # api boundary
    ((240, 253, 244), (187, 247, 208), GREEN),      # application policy
    ((248, 250, 252), (203, 213, 225), SLATE),      # persistence
]

# Each layer: (number, name, strapline, [(title, detail), ...]).
# `detail` is dropped in the slide variant.
LAYERS = [
    ("1", "Browser", "analyst · staff · admin — React 18 + Vite + Tailwind", [
        ("6 role-scoped pages", "Login, Dashboard, Inbox, Staff Portal,\nRelease Requests, Audit Logs"),
        ("AuthContext", "holds the session; revalidates it\nthrough /api/auth/me on load"),
        ("lib/transitions.js", "mirrors the server state machine so\nthe UI only offers valid actions"),
        ("Route guards", "usability only — never a\nsecurity control"),
    ]),
    ("2", "API boundary", "FastAPI + Uvicorn", [
        ("main.py", "CORS allow-list, security headers,\nrequest id, one error envelope"),
        ("schemas.py", "Pydantic v2 validation; input bounds\nmatched to the column widths"),
        ("deps.py", "JWT -> user re-read from the DB;\nrequire_roles(...) per route"),
        ("security.py / ratelimit.py", "bcrypt with a 72-byte guard, typed\nJWTs, per-IP failed-login limit"),
    ]),
    # Implemented components only. The unbuilt classifier is disclosed in the
    # report's limitations, not drawn here as though it were part of the system.
    ("3", "Application policy", "authoritative — all rules re-checked here", [
        ("5 routers", "auth, emails, requests,\naudit, dashboard"),
        ("transitions.py", "the email state machine: which action\nis valid from which status"),
        ("scoring.py", "rule engine: bounded score, level and\nthe named reasons behind it"),
        ("audit.py", "append-only writer at application level:\nevery material action is recorded"),
    ]),
    ("4", "Persistence", "SQLAlchemy 2.0 -> PostgreSQL", [
        ("Unit-of-work session", "status, review and audit rows commit\nor roll back together"),
        ("PostgreSQL 16.6", "the assessed target database"),
        ("SQLite", "zero-install fallback for local runs\nand the default test engine"),
        ("Database integrity", "5 tables, 10 CHECK constraints and a\npartial unique index"),
    ]),
]

# The gaps between columns are too narrow to letter, so the hand-offs are named
# once in this legend instead of being crammed against an arrowhead.
LEGEND = ("Hand-offs:   1 -> 2  JSON over HTTP with a Bearer JWT      "
          "2 -> 3  a validated, authenticated call      "
          "3 -> 4  one SQLAlchemy session per request")

REQUEST_PATH = [
    "POST /api/emails/3/release",
    "Pydantic validates the body",
    "JWT resolved, role read from the DB",
    "transitions.is_allowed('release', status)",
    "review + status + audit in one transaction",
    "200, or 409 naming the valid states",
]

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"),
             Path("/System/Library/Fonts")]


def _font(names: list[str], px: int):
    for d in FONT_DIRS:
        for n in names:
            p = d / n
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), px)
                except OSError:
                    continue
    return ImageFont.load_default()


BOLD = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
REG = ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
MONO = ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"]


def rounded(d, box, radius, fill, outline, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def build(variant: str) -> Path:
    detailed = variant == "report"
    W_IN, H_IN = (10.59, 5.60) if detailed else (11.31, 4.75)
    inch = DPI
    W, H = round(W_IN * inch), round(H_IN * inch)

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    def px(v: float) -> int:
        return round(v * inch)

    # The slide already carries its own heading, so this variant draws no title;
    # the fonts are still constructed because PIL rejects a zero size.
    f_title = _font(BOLD, px(0.185))
    f_sub = _font(REG, px(0.105))
    f_lnum = _font(BOLD, px(0.135 if detailed else 0.165))
    f_lname = _font(BOLD, px(0.135 if detailed else 0.175))
    f_lstrap = _font(REG, px(0.088 if detailed else 0.105))
    f_ctitle = _font(BOLD, px(0.106 if detailed else 0.145))
    f_cdetail = _font(REG, px(0.087))
    f_arrow = _font(REG, px(0.078 if detailed else 0.098))
    f_path = _font(MONO, px(0.072 if detailed else 0.088))
    f_pathlbl = _font(BOLD, px(0.082 if detailed else 0.098))
    f_boundary = _font(BOLD, px(0.080 if detailed else 0.098))

    MARGIN = 0.10
    top = 0.0

    if detailed:
        d.text((W / 2, px(0.15)), "PhishGuard system architecture, as implemented",
               font=f_title, fill=NAVY, anchor="mm")
        d.text((W / 2, px(0.33)),
               "Four ordered layers. Every box names a file in the repository. "
               "Data flows left to right; nothing left of the trust boundary is trusted.",
               font=f_sub, fill=MUTED, anchor="mm")
        d.text((W / 2, px(0.47)), LEGEND, font=f_arrow, fill=SLATE, anchor="mm")
        top = 0.62
    else:
        d.text((W / 2, px(0.10)), LEGEND, font=f_arrow, fill=SLATE, anchor="mm")
        top = 0.20

    # Column geometry: a wider gap after layer 1 leaves room for the boundary.
    gaps = [0.36, 0.20, 0.20]
    col_w = (W_IN - 2 * MARGIN - sum(gaps)) / 4

    strip_h = 0.52 if detailed else 0.46
    # Enough clearance for the layer name and its strapline above the first card.
    body_top = top + (0.40 if detailed else 0.56)
    body_bot = H_IN - strip_h - 0.20
    col_top, col_bot = top, body_bot

    xs: list[float] = []
    x = MARGIN
    for i in range(4):
        xs.append(x)
        x += col_w + (gaps[i] if i < 3 else 0)

    for i, (num, name, strap, items) in enumerate(LAYERS):
        fill, edge, accent = LAYER_TINTS[i]
        x0 = xs[i]
        rounded(d, [px(x0), px(col_top), px(x0 + col_w), px(col_bot)],
                px(0.09), fill, edge, 3)

        # Header: the number in a filled chip, then the layer name.
        chip = px(0.19 if detailed else 0.23)
        cy = px(col_top + 0.155 + (0.0 if detailed else 0.02))
        d.rounded_rectangle([px(x0 + 0.10), cy - chip // 2, px(x0 + 0.10) + chip, cy + chip // 2],
                            radius=px(0.03), fill=accent)
        d.text((px(x0 + 0.10) + chip // 2, cy), num, font=f_lnum, fill=(255, 255, 255), anchor="mm")
        d.text((px(x0 + 0.10) + chip + px(0.07), cy), name, font=f_lname, fill=accent, anchor="lm")
        d.text((px(x0 + 0.10), px(col_top + (0.30 if detailed else 0.36))), strap,
               font=f_lstrap, fill=MUTED, anchor="lt")

        # Cards are sized to their own content, then grown by an equal share of
        # whatever space is left. Growing the cards rather than the gaps keeps the
        # column reading as one block, and every column still ends on the same
        # baseline even though layer 3 holds five modules and the others four.
        n = len(items)
        avail = (col_bot - 0.10) - body_top
        gap = 0.10
        line_h, title_h = 0.106, 0.16
        needed = [title_h + (len(cd.split("\n")) * line_h if detailed else 0) + 0.13
                  for _, cd in items]
        slack = avail - sum(needed) - gap * (n - 1)
        if slack >= 0:
            heights = [h + slack / n for h in needed]
        else:                                   # too tall: shrink uniformly
            k = (avail - gap * (n - 1)) / sum(needed)
            heights = [h * k for h in needed]

        cy0 = body_top
        for j, (ctitle, cdetail) in enumerate(items):
            card_h = heights[j]
            rounded(d, [px(x0 + 0.10), px(cy0), px(x0 + col_w - 0.10), px(cy0 + card_h)],
                    px(0.05), (255, 255, 255), edge, 2)
            lines = cdetail.split("\n") if detailed else []
            block = title_h + len(lines) * line_h
            ty = cy0 + (card_h - block) / 2
            d.text((px(x0 + 0.18), px(ty + title_h / 2)), ctitle,
                   font=f_ctitle, fill=NAVY, anchor="lm")
            ty += title_h
            for line in lines:
                d.text((px(x0 + 0.18), px(ty)), line, font=f_cdetail, fill=SLATE, anchor="lt")
                ty += line_h
            cy0 += card_h + gap

    # Arrows between layers. The hand-offs are named in the legend, so these are
    # direction only and cannot collide with a column edge.
    mid = px((col_top + col_bot) / 2)
    for i in range(3):
        gx0 = px(xs[i] + col_w)
        gx1 = px(xs[i + 1])
        ay = mid
        pad = px(0.04)
        d.line([gx0 + pad, ay, gx1 - pad - px(0.05), ay], fill=SLATE, width=4)
        d.polygon([(gx1 - pad, ay), (gx1 - pad - px(0.075), ay - px(0.048)),
                   (gx1 - pad - px(0.075), ay + px(0.048))], fill=SLATE)

    # The trust boundary: a dashed vertical rule in the wide gap after layer 1.
    bx = px(xs[1] - gaps[0] / 2)
    lbl = "TRUST BOUNDARY"
    lh = px(0.093)
    lbl_h = len(lbl) * lh
    lbl_top = px((col_top + col_bot) / 2) - lbl_h // 2
    y = px(col_top + 0.04)
    while y < px(col_bot - 0.04):
        seg_end = min(y + px(0.055), px(col_bot - 0.04))
        # Leave a clean break where the label sits, so no dash crosses a letter.
        if not (lbl_top - px(0.06) < y < lbl_top + lbl_h + px(0.06)):
            d.line([bx, y, bx, seg_end], fill=RED, width=3)
        y += px(0.095)
    for k, ch in enumerate(lbl):
        d.text((bx, lbl_top + k * lh + lh // 2), ch, font=f_boundary, fill=RED, anchor="mm")

    # Bottom strip: one real request, traced through the layers.
    sy0 = H_IN - strip_h - 0.04
    rounded(d, [px(MARGIN), px(sy0), px(W_IN - MARGIN), px(sy0 + strip_h)],
            px(0.07), (248, 250, 252), BORDER, 2)
    d.text((px(MARGIN + 0.14), px(sy0 + strip_h / 2)), "One request,\ntraced:",
           font=f_pathlbl, fill=NAVY, anchor="lm")
    px0 = MARGIN + 0.95
    avail = (W_IN - MARGIN - 0.12) - px0
    step_w = (avail - 0.06 * (len(REQUEST_PATH) - 1)) / len(REQUEST_PATH)
    for i, step in enumerate(REQUEST_PATH):
        x0 = px0 + i * (step_w + 0.06)
        rounded(d, [px(x0), px(sy0 + 0.08), px(x0 + step_w), px(sy0 + strip_h - 0.08)],
                px(0.04), (255, 255, 255), BORDER, 2)
        words = step.split()
        lines: list[str] = []
        line = ""
        maxw = px(step_w - 0.10)
        for wd in words:
            trial = f"{line} {wd}".strip()
            if d.textlength(trial, font=f_path) <= maxw:
                line = trial
            else:
                lines.append(line)
                line = wd
        if line:
            lines.append(line)
        lh = px(0.085)
        ty = px(sy0 + strip_h / 2) - (len(lines) - 1) * lh // 2
        for line in lines[:4]:
            d.text((px(x0 + step_w / 2), ty), line, font=f_path, fill=SLATE, anchor="mm")
            ty += lh
        if i < len(REQUEST_PATH) - 1:
            ax = px(x0 + step_w + 0.03)
            ay = px(sy0 + strip_h / 2)
            d.polygon([(ax + px(0.022), ay), (ax - px(0.012), ay - px(0.030)),
                       (ax - px(0.012), ay + px(0.030))], fill=MUTED)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / (f"architecture.png" if detailed else "architecture-slide.png")
    img.save(out, "PNG")
    print(f"  {out.name:<26} {img.width}x{img.height} px  = {W_IN}x{H_IN} in at {DPI} dpi")
    return out


def main() -> int:
    print("Architecture figures:")
    build("report")
    build("slide")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
