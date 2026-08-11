"""Build the report's core-workflow figure from four genuine screenshots.

Every pane is a crop of a real capture in evidence/screenshots — no mock-up, no
redrawing, and no image lifted out of the slide deck. The uncropped originals are
reproduced full page in the report appendix.

Why the layout is what it is
----------------------------
The figure has to be readable at 100% zoom in the PDF, and physical text size on
the page depends only on how many CSS pixels of interface are squeezed into how
many inches of paper. The screenshots are 1600 CSS pixels wide, captured at
device scale 2, so a full screen shrunk into an A4 column renders 14px interface
text at roughly 2pt — illegible. Two things fix that:

  1. The figure occupies a full landscape page, not a portrait column.
  2. Panes are laid out by aspect ratio rather than in a rigid 2x2 grid. Step 4
     is a wide table, so it gets a full-width row of its own; the three
     narrower panes share the row above. Every pane then lands between about
     6pt and 9pt of effective interface text.

Run after evidence/capture_screenshots.py, since the crop boxes below are tied to
what those captures contain.

Usage:
    python evidence/make_workflow_figure.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "screenshots"
OUT = HERE / "figures" / "core-workflow.png"

# The landscape page area the figure is placed into, in inches: A4 landscape
# (11.69 x 8.27) less the report's 0.55in margins is 10.59 x 7.17, and the height
# here leaves room for the caption beneath. finalise_report.py inserts the image at
# exactly this size, so what is computed below is what the reader sees.
PAGE_W_IN, PAGE_H_IN = 10.59, 6.60
DPI = 288

# Crop boxes are in image pixels on the 3200x2000 captures, i.e. 2x the CSS
# position. Each box is framed on whole interface elements: no box cuts through a
# line of text, which is what went wrong in the first version of this figure.
PANES = [
    # (file, crop, step label, caption)
    # Bottom edge sits on the row divider after IT Helpdesk, so no email row is
    # sliced in half.
    ("04-analyst-inbox.png", (585, 235, 1465, 1075),
     "1. Triage",
     "Every message is scored on arrival and the inbox is ordered by risk, so the "
     "worst mail is reviewed first."),

    # Right edge sits in the gap after the DKIM card. The DMARC card is outside
    # the frame rather than cut through it; Appendix C shows the full row.
    ("06-email-detail-explainable-score.png", (1530, 690, 2735, 1665),
     "2. Explain",
     "The score is never an opaque number: the panel names the indicator behind "
     "every point it awarded."),

    ("10-release-request-validation.png", (1176, 680, 2024, 1328),
     "3. Challenge",
     "The recipient can ask for a held message back, with a justification the form "
     "refuses to submit until it is long enough."),

    ("13-release-request-approved.png", (575, 245, 3150, 885),
     "4. Decide",
     "Only an analyst or an administrator decides. Approval releases the email and writes the "
     "review and audit rows in the same transaction."),
]

# No title or subtitle is drawn inside the figure. The report supplies the caption,
# and every line of chrome the figure draws is a line the screenshots do not get —
# which is the whole constraint here, since pane width is what sets legibility.

NAVY = (15, 23, 42)
BRAND = (37, 99, 235)
MUTED = (71, 85, 105)
BORDER = (203, 213, 225)
BG = (255, 255, 255)

# Vertical budget, in inches. Every tenth of an inch spent here is taken off the
# pane widths, so these are as tight as the type allows: a caption is at most two
# lines of 0.108in, and a step label one line of 0.135in.
HEADER_H = 0.0
STEP_H = 0.22
CAP_H = 0.30
GAP_X = 0.10
GAP_Y = 0.14

FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu"),
             Path("/System/Library/Fonts")]


def _font(names: list[str], px: int) -> ImageFont.ImageFont:
    for d in FONT_DIRS:
        for n in names:
            p = d / n
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), px)
                except OSError:
                    continue
    return ImageFont.load_default()


def wrap(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    out: list[str] = []
    line = ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=font) <= width:
            line = trial
        else:
            out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def main() -> int:
    inch = DPI

    crops = [Image.open(SHOTS / name).convert("RGB").crop(box)
             for name, box, _, _ in PANES]
    aspects = [c.width / c.height for c in crops]

    # Row 1 holds the three narrow panes at a common height; row 2 is pane 4
    # alone across the full width.
    row1_w = PAGE_W_IN - 2 * GAP_X
    h1 = row1_w / sum(aspects[:3])
    h2 = PAGE_W_IN / aspects[3]

    fixed = HEADER_H + 2 * (STEP_H + CAP_H) + GAP_Y
    if fixed + h1 + h2 > PAGE_H_IN:            # shrink both rows to fit the page
        k = (PAGE_H_IN - fixed) / (h1 + h2)
        h1, h2 = h1 * k, h2 * k

    W = round(PAGE_W_IN * inch)
    H = round((fixed + h1 + h2) * inch)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    f_title = _font(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], round(0.20 * inch))
    f_sub = _font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], round(0.115 * inch))
    f_step = _font(["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], round(0.135 * inch))
    f_cap = _font(["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], round(0.108 * inch))

    def place(crop: Image.Image, x_in: float, y_in: float, w_in: float, h_in: float,
              step: str, caption: str) -> None:
        """Draw one pane: step label, image scaled to w_in x h_in, then caption."""
        x, y = round(x_in * inch), round(y_in * inch)
        w, h = round(w_in * inch), round(h_in * inch)
        d.text((x, y + round(STEP_H * inch / 2)), step, font=f_step, fill=BRAND, anchor="lm")
        top = y + round(STEP_H * inch)
        img.paste(crop.resize((w, h), Image.LANCZOS), (x, top))
        d.rectangle([x, top, x + w, top + h], outline=BORDER, width=3)
        ty = top + h + round(0.13 * inch)
        for line in wrap(d, caption, f_cap, w)[:3]:
            d.text((x, ty), line, font=f_cap, fill=NAVY, anchor="lm")
            ty += round(0.135 * inch)

    y_row1 = HEADER_H
    x = 0.0
    for i in range(3):
        w_in = h1 * aspects[i]
        place(crops[i], x, y_row1, w_in, h1, PANES[i][2], PANES[i][3])
        x += w_in + GAP_X

    y_row2 = HEADER_H + STEP_H + h1 + CAP_H + GAP_Y
    place(crops[3], 0.0, y_row2, PAGE_W_IN, h2, PANES[3][2], PANES[3][3])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")

    print(f"Workflow figure written: {OUT}  ({img.width}x{img.height} px, "
          f"{img.width / inch:.2f}x{img.height / inch:.2f} in at {DPI} dpi)")
    for i, (name, box, step, _) in enumerate(PANES):
        w_in = PAGE_W_IN if i == 3 else h1 * aspects[i]
        css_w = (box[2] - box[0]) / 2          # captures are device scale 2
        print(f"  {step:<12} {name:<44} {w_in:5.2f}in wide for {css_w:4.0f} CSS px "
              f"-> 14px interface text renders at {14 * w_in / css_w * 72:.1f}pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
