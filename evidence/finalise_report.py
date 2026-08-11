"""Finalise the PhishGuard report: edit the existing DOCX, do not rebuild it.

This is the last pass over the report. Earlier passes (update_report.py,
trim_report.py, trim_report2.py) corrected figures and fitted the word
allocation. This one:

  * removes every placeholder, internal warning box and unfinished checklist,
    replacing the four fields only the student can supply with ruled fill-in
    lines rather than "[Insert ...]" text;
  * updates the verified figures to the 11 August 2026 run (170 backend tests on
    both engines, 90% coverage, 92 frontend tests, 22 live checks) and corrects
    the two arithmetic slips that survived the earlier passes;
  * enlarges the architecture diagram and adds the data-model figure and the
    composite workflow figure, each on its own landscape page;
  * adds the appendices the rubric asks for — representative test cases with
    expected and actual results, a planned-versus-completed matrix, the
    problem/fix/regression log, CI and release evidence, and full-page
    screenshots;
  * moves table captions above their tables and pins them there, so a caption can
    no longer be orphaned from the table it describes.

The document keeps its own styles, colours, header, page numbering and layout
throughout: nothing here creates a new document or a new theme.

Usage:
    python evidence/finalise_report.py <input.docx> <output.docx>
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
FIGURES = HERE / "figures"
SHOTS = HERE / "screenshots"

REPO_URL = "https://github.com/Toolstack7462/Mit208"
# The assessed version. The earlier *-final tags are intermediate markers, left
# exactly where they point rather than moved, so the history stays honest.
TAG = "v1.3-final"
TAG_URL = f"{REPO_URL}/releases/tag/{TAG}"
BLANK = "_" * 34            # a ruled fill-in field, not a placeholder to delete

# Table look, lifted from the tables already in the document so new tables are
# indistinguishable from the existing one.
HEAD_FILL = "173B5D"
ZEBRA_FILL = "F4F7F9"
GRID = "CFD8DF"
BODY_COLOUR = RGBColor(0x1C, 0x28, 0x33)
FONT = "Carlito"
CELL_PT = Pt(8.5)


# ---------------------------------------------------------------------------
# Low-level document helpers
# ---------------------------------------------------------------------------

def body_paragraphs(doc) -> list[Paragraph]:
    return doc.paragraphs


def find(doc, needle: str) -> Paragraph:
    """The one paragraph that starts with ``needle``. Fails loudly if ambiguous."""
    hits = [p for p in doc.paragraphs if p.text.strip().startswith(needle)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one paragraph starting {needle!r}, found {len(hits)}")
    return hits[0]


def set_text(p: Paragraph, text: str) -> None:
    """Replace a paragraph's text, keeping the formatting of its first run."""
    if not p.runs:
        p.add_run(text)
        return
    p.runs[0].text = text
    for r in p.runs[1:]:
        r.text = ""


def para_after(ref, style: str | None = None) -> Paragraph:
    """A new, empty paragraph immediately after ``ref`` (a Paragraph or Table)."""
    new = OxmlElement("w:p")
    anchor = ref._p if isinstance(ref, Paragraph) else ref._tbl
    anchor.addnext(new)
    p = Paragraph(new, ref._parent)
    if style:
        p.style = style
    return p


def delete(el) -> None:
    node = el._p if isinstance(el, Paragraph) else el._tbl
    node.getparent().remove(node)


def set_sectpr(p: Paragraph, source_sectpr) -> None:
    """Make ``p`` the last paragraph of a section shaped like ``source_sectpr``."""
    pPr = p._p.get_or_add_pPr()
    pPr.append(copy.deepcopy(source_sectpr))


def compact(p: Paragraph) -> None:
    """A section-break carrier should not add a visible blank line."""
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("")
    run.font.size = Pt(1)


def keep_with_next(p: Paragraph) -> None:
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.widow_control = True


def pin_table_rows(table: Table) -> None:
    """Stop a table row splitting across a page, and keep the header repeating."""
    for row in table.rows:
        trPr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        trPr.append(cant)
    header = table.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader")
    th.set(qn("w:val"), "true")
    header.append(th)


# ---------------------------------------------------------------------------
# Table construction, matching the document's existing table formatting
# ---------------------------------------------------------------------------

def _shade(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _borders(table: Table) -> None:
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "start", "bottom", "end", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "5")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), GRID)
        borders.append(el)
    tblPr.append(borders)


def _write_cell(cell, text: str, *, bold: bool, white: bool) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    run = p.add_run(text)
    run.font.name = FONT
    run.font.size = CELL_PT
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if white else BODY_COLOUR


def build_table(doc, after, rows: list[list[str]], widths: list[float]) -> Table:
    """Create a themed table after ``after``. ``rows[0]`` is the header."""
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    anchor = after._p if isinstance(after, Paragraph) else after._tbl
    anchor.addnext(table._tbl)
    table.autofit = False
    _borders(table)

    for ri, row in enumerate(rows):
        for ci, text in enumerate(row):
            cell = table.cell(ri, ci)
            cell.width = Inches(widths[ci])
            _write_cell(cell, text, bold=(ri == 0), white=(ri == 0))
            if ri == 0:
                _shade(cell, HEAD_FILL)
            elif ri % 2 == 0:
                _shade(cell, ZEBRA_FILL)
    pin_table_rows(table)
    return table


def add_caption(doc, after, text: str, *, above: bool) -> Paragraph:
    p = para_after(after, style="Caption")
    set_text(p, text)
    if above:
        # A table caption sits above its table and must not be left behind on the
        # previous page, which is what "keep every table caption with its table"
        # means in practice.
        keep_with_next(p)
    return p


# ---------------------------------------------------------------------------
# Landscape figure pages
# ---------------------------------------------------------------------------

def landscape_figure(doc, after, image: Path, caption: str,
                     width_in: float, height_in: float, portrait_sectpr,
                     landscape_sectpr, *, after_landscape: bool = False,
                     pre: list[tuple[str, str]] | None = None):
    """Put one image and its caption on a landscape page of their own.

    Returns the trailing section-break paragraph, so blocks can be chained.

    ``after_landscape`` must be True when ``after`` is itself the trailing break of
    a landscape block. A sectPr terminates the section that ends at its paragraph,
    so emitting a portrait terminator there would create a section containing one
    empty paragraph — a blank portrait page between two landscape figures.

    ``pre`` places (style, text) paragraphs inside the landscape section above the
    image. An appendix heading left in the preceding portrait section would sit
    alone on a page of its own, because the section break starts a new page.
    """
    if not image.exists():
        raise SystemExit(f"figure missing: {image}")

    anchor = after
    if not after_landscape:
        end_portrait = para_after(after)
        compact(end_portrait)
        set_sectpr(end_portrait, portrait_sectpr)
        anchor = end_portrait

    for style, text in (pre or []):
        p = para_after(anchor, style=style)
        set_text(p, text)
        keep_with_next(p)
        anchor = p

    pic = para_after(anchor)
    pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic.paragraph_format.space_before = Pt(0)
    pic.paragraph_format.space_after = Pt(4)
    pic.add_run().add_picture(str(image), width=Inches(width_in), height=Inches(height_in))

    cap = para_after(pic, style="Caption")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_text(cap, caption)

    end_landscape = para_after(cap)
    compact(end_landscape)
    set_sectpr(end_landscape, landscape_sectpr)
    return end_landscape


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

TITLE_ROWS = {
    "STUDENT NAME": BLANK,
    "STUDENT ID": BLANK,
    "LECTURER": BLANK,
    "SUBMISSION DATE": BLANK,
    "FINAL RELEASE": f"Tag {TAG} — {TAG_URL}",
}

BODY = {
    # --- Executive summary ---------------------------------------------------
    "PhishGuard is a student prototype": (
        "PhishGuard is a student prototype for triaging suspicious email and "
        "controlling quarantine and release decisions. It gives analysts explainable "
        "risk evidence and staff a governed way to challenge a held message. It "
        "combines React, FastAPI and SQLAlchemy over PostgreSQL, with SQLite as a "
        "local fallback. Detection is a transparent rule-based score, not a trained "
        "model. The implementation completes the core workflow and enforces role and "
        "state rules on the server and in the database. It is verified by 170 backend "
        "tests at 90 per cent statement coverage on both SQLite and PostgreSQL 16.6, "
        "92 frontend tests, and 22 live API checks per engine, plus 24 screenshots and "
        "a four-minute walkthrough of the running application."
    ),

    # --- 1. Background and objectives ---------------------------------------
    "Phishing review is difficult": (
        "Phishing review is difficult when users receive only a warning without "
        "evidence, or when a held message cannot be challenged through a controlled "
        "process. PhishGuard was designed for two groups: analysts who review risk "
        "indicators and staff whose synthetic messages may be held. The "
        "final MVP objectives were to authenticate role-based users; score sample "
        "emails with understandable reasons; display dashboard and inbox information; "
        "allow analysts to quarantine, release or confirm phishing only from valid "
        "states; allow staff to request release of their own held email; and record "
        "relevant actions in an audit trail. Appendix C sets out what was planned "
        "against what was completed. The project deliberately excludes live mailbox "
        "integration, production deployment and trained text classification. SPF, DKIM "
        "and DMARC values are simulated because the samples contain no real SMTP "
        "headers. These boundaries keep the prototype defensible rather than "
        "presenting it as production-grade protection."
    ),

    # --- 2. Lifecycle and management ----------------------------------------
    "The public repository shows": (
        "The public repository shows an incremental implementation journey rather than "
        "one final upload. The first nine commits, between June and July 2026, cover "
        "the initial full-stack MVP, interface redesign, weekly dashboard chart, more "
        "realistic sample timestamps, documentation and screenshots, then backend tests "
        "and test documentation. Further commits in August 2026 carry the hardening "
        "below, separated by concern so the history stays readable. During "
        "the final review I compared the code, tests and documentation against the "
        "Assessment 3 criteria rather than relying on README claims. This exposed a "
        "difference between restrictions shown in the interface and rules enforced "
        "authoritatively by the API. I kept the existing architecture and prioritised "
        "high-value corrections: an explicit state machine, duplicate-request "
        "prevention, authorisation read from the database rather than the token, atomic "
        "transactions, database constraints, clearer interface states, frontend tests, "
        "continuous integration and organised evidence. Work was planned by risk: "
        "security defects first, reproducibility second, presentation last. Optional "
        "DistilBERT work stayed out of scope, because an "
        "unverified classifier would have weakened the defensibility of the working MVP."
    ),

    # --- 3. Design and architecture -----------------------------------------
    "The final design uses": (
        "The final design uses the layered web architecture shown in Figure 1. React "
        "and React Router present role-specific pages and use Axios to send "
        "bearer-token requests. FastAPI routers separate authentication, email, "
        "dashboard, release-request and audit operations. Pydantic schemas validate the "
        "API boundary, and a central dependency reloads the active user from the "
        "database on every request. Authorisation uses that stored role only: the role "
        "inside the token is display information and is never trusted, so a tampered "
        "claim grants nothing. SQLAlchemy models coordinate the five tables in "
        "Figure 2 — users, email records, analyst reviews, release requests and audit "
        "events. PostgreSQL is the assessed target; SQLite provides a reproducible "
        "local and test fallback. The deterministic scoring module adds bounded points "
        "for indicators such as impersonation, urgency, credential requests and "
        "suspicious links, then stores a score, level and human-readable reasons. One "
        "module declares which action is valid from which status, and both routes that "
        "can move an email import it. This design keeps policy on the server, limits "
        "staff data by recipient and uses database constraints as a final integrity "
        "guard."
    ),

    # --- 4. Implementation and technology -----------------------------------
    "React 18 and Vite": (
        "React 18 and Vite were retained because the interface was already "
        "componentised and suited to a local demonstration. Shared authentication state "
        "revalidates a cached session through /api/auth/me on load, discarding a stale "
        "stored user. Every data page has distinct loading, empty and failure states, "
        "with a retry action and a reference identifier matching the server log. "
        "Figure 3 shows the four screens of the core workflow; Appendix F reproduces "
        "them full page."
    ),
    "FastAPI suited typed request handling": (
        "FastAPI suited typed request handling and automatic OpenAPI documentation "
        "(FastAPI, n.d.). Authentication uses bcrypt hashes and expiring signed JSON "
        "Web Tokens. Password handling respects bcrypt's 72-byte limit and refuses "
        "longer input rather than truncating it, since truncation would make two "
        "different long passwords interchangeable. Tokens carry issued-at, "
        "unique-identifier and token-type claims, so a token can be traced in a log and "
        "one minted for another purpose cannot be replayed. Protected routes confirm the "
        "user is still active, so deactivation takes effect immediately (OWASP "
        "Foundation, n.d.; Jones, Bradley and Sakimura, 2015)."
    ),
    "The most important backend change": (
        "The most important backend change was turning workflow assumptions into "
        "explicit policy. Every action now declares the statuses it may be applied "
        "from, so releasing an email that was never withheld is refused with a conflict "
        "before any row is written; previously only a repeat was refused. One module "
        "holds that table, both routes that can move an email import it, and the "
        "interface mirrors it. Release requests are staff-only and limited to the "
        "caller's own held mail. Transactions commit status, review and audit rows "
        "together and roll back on failure, a unit of work (SQLAlchemy, 2026). "
        "Constraints in the ORM and the schema restrict role, status and decision "
        "values, and a partial unique index guards duplicates (PostgreSQL Global "
        "Development Group, 2026a; 2026b)."
    ),

    # --- 5. Testing, security and results -----------------------------------
    "Testing combines unit": (
        "Testing combines unit and API tests with a running-server smoke workflow. "
        "170 backend tests pass at 90 per cent statement coverage (847 of 943 "
        "statements) on both SQLite and PostgreSQL 16.6; only the classifier placeholder "
        "and the seeding script are uncovered. Twenty-two live checks against a running "
        "server, repeated on each engine, cover login, staff data isolation, valid and "
        "invalid transitions, duplicates, approval and audit access. On the frontend, "
        "92 tests render real components in jsdom, covering route and role policy, error "
        "mapping, login and the release-request rules. Negative cases include forged and "
        "expired tokens, a tampered role claim, over-long input and malformed stored "
        "score reasons. Table 1 summarises the run; Appendix B lists representative "
        "cases with expected and actual results."
    ),
    "Security controls include": (
        "Security controls include bcrypt hashes, expiring typed JWTs, server-side role "
        "checks, per-IP limiting of failed logins, input bounds matched to the column "
        "widths, ownership filtering, explicit CORS, security headers and constraints "
        "that reject impossible rows. Login answers an unknown address and a wrong "
        "password identically, so it cannot reveal which accounts exist. The audit trail "
        "is append-only at application level — no route updates or deletes a row — "
        "though a database administrator could. These controls suit a student prototype, "
        "not production security: there is no multi-factor authentication, token "
        "revocation, tamper-evident logging or local HTTPS, and the rate limiter counts "
        "within one process. Against PostgreSQL 16.6 the schema applied cleanly, ten "
        "check constraints and the partial unique index were confirmed, and six invalid "
        "writes were rejected; a committed secret scan reports no credential in any "
        "tracked file (NIST, 2022)."
    ),

    # --- 6. Problems, changes and limitations -------------------------------
    "Two significant defects": (
        "Two defects shaped the final changes. First, any analyst action was accepted "
        "from any state: only a repeat was refused, so an email that had never been held "
        "could be released, recording a decision nobody made in the very trail meant to "
        "hold analysts accountable. An explicit action-to-source-state table now governs "
        "both routes that can move an email. Second, the ownership check on release "
        "requests tested the caller's role before comparing the recipient, so an analyst "
        "or administrator could raise a request against any mailbox, recording a release "
        "the recipient never asked for. That endpoint is now staff-only."
    ),
    "A third problem was malformed JSON": (
        "A third problem was malformed JSON in the stored scoring reasons: the handler "
        "parsed that column directly, so one corrupt row made its message permanently "
        "unopenable. Defensive parsing now substitutes a placeholder, and a regression "
        "test corrupts a row to prove it. Appendix D records each problem with its fix "
        "and the "
        "test that would catch its return. Remaining limitations are synthetic data, "
        "simulated authentication headers, a heuristic AI-generated label, an "
        "unimplemented DistilBERT placeholder, browser-stored tokens and no "
        "browser-level test."
    ),

    # --- 7. Evaluation and reflection ---------------------------------------
    "The prototype meets its functional objectives": (
        "The prototype meets its functional objectives. Analysts can authenticate, "
        "inspect explainable indicators and apply validated "
        "actions. Staff data is scoped by recipient, and a staff member can raise one "
        "controlled release request for an owned held message; approval updates "
        "request, email, review and audit records together. My strongest learning "
        "outcome was that interface restrictions are not security controls: every role, "
        "ownership and state rule must be rechecked server-side and, where possible, "
        "backed by a database constraint. I also learned that a high test count matters "
        "less than representative positive, negative, integration and regression "
        "scenarios tied to genuine defects."
    ),
    "Passing local tests": (
        "Passing local tests is not the same as being submission-complete. The "
        "continuous-integration run passes on the public repository and the assessed "
        "commit carries a tag, both evidenced in Appendix E; Appendix A maps every claim "
        "here to the file that supports it, and Appendix G declares my use of generative "
        "AI. What remains is mine: recording the narration over the silent capture and "
        "rehearsing the code explanation. Future work should add a browser-level test "
        "and stronger session controls."
    ),

    # --- Conclusion ----------------------------------------------------------
    "PhishGuard demonstrates a coherent": (
        "PhishGuard demonstrates a coherent, explainable phishing-triage workflow with "
        "role-based access, validated state changes, controlled release requests, audit "
        "evidence and repeatable testing. The final review improved reliability and "
        "security without replacing the architecture or overstating the rule engine as "
        "machine learning. It is supported by 262 automated tests, 22 live API checks on "
        "each database engine, 24 labelled screenshots and a recording of the running "
        "application, all reproducible from the repository. The honest remaining gap is "
        "the recorded narration. Realistic next steps are a browser-level test suite and "
        "stronger session controls."
    ),
}

REFERENCES = {
    "FastAPI (n.d.)": (
        "FastAPI (n.d.) OAuth2 with Password (and hashing), Bearer with JWT tokens. "
        "Available at: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ "
        "(Accessed: 11 August 2026)."
    ),
    "Jones, M.": (
        "Jones, M., Bradley, J. and Sakimura, N. (2015) JSON Web Token (JWT), RFC 7519. "
        "Internet Engineering Task Force. Available at: "
        "https://www.rfc-editor.org/rfc/rfc7519 (Accessed: 11 August 2026)."
    ),
    "National Institute of Standards": (
        "National Institute of Standards and Technology (2022) Secure Software "
        "Development Framework (SSDF) Version 1.1, NIST SP 800-218. Gaithersburg, MD: "
        "NIST."
    ),
    "OWASP Foundation (n.d.)": (
        "OWASP Foundation (n.d.) Password Storage Cheat Sheet. Available at: "
        "https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html "
        "(Accessed: 11 August 2026)."
    ),
    # The prototype is verified on 16.6, so the cited manual is the 16 series.
    "PostgreSQL Global Development Group (2026a)": (
        "PostgreSQL Global Development Group (2026a) PostgreSQL 16 Documentation: "
        "Constraints. Available at: "
        "https://www.postgresql.org/docs/16/ddl-constraints.html "
        "(Accessed: 11 August 2026)."
    ),
    "PostgreSQL Global Development Group (2026b)": (
        "PostgreSQL Global Development Group (2026b) PostgreSQL 16 Documentation: "
        "Partial Indexes. Available at: "
        "https://www.postgresql.org/docs/16/indexes-partial.html "
        "(Accessed: 11 August 2026)."
    ),
    "SQLAlchemy authors": (
        "SQLAlchemy authors (2026) SQLAlchemy 2.0 Documentation: Session Basics. "
        "Available at: https://docs.sqlalchemy.org/en/20/orm/session_basics.html "
        "(Accessed: 11 August 2026)."
    ),
    "Toolstack7462 (2026)": (
        f"Toolstack7462 (2026) Mit208: PhishGuard [GitHub repository]. Available at: "
        f"{REPO_URL} (Accessed: 11 August 2026)."
    ),
}

TABLE1 = [
    ["Evidence layer", "Verified result", "Environment and qualification"],
    ["Backend tests (pytest 9.1.1)", "170 passed",
     "In-memory SQLite, then the same suite on PostgreSQL 16.6"],
    ["Statement coverage", "90% (847 of 943)",
     "Uncovered: the classifier placeholder and the seeding script"],
    ["Live API smoke workflow", "22 of 22 passed",
     "Real running server, repeated on each engine"],
    ["Frontend tests (vitest)", "92 passed across 11 files",
     "jsdom; production build 1,655 modules in 16.70s"],
    ["Database integrity, raw SQL", "6 of 6 invalid writes rejected",
     "PostgreSQL 16.6: ten CHECK constraints and a partial unique index"],
    ["Secret scan", "0 unacknowledged findings",
     "Every tracked file; also enforced as a CI job"],
]

APPENDIX_A = [
    ["Report claim", "Repository evidence", "How to verify it"],
    ["Core analyst and staff workflow completes end to end",
     "backend/app/routers/, frontend/src/pages/, 170 backend and 92 frontend tests",
     "Run smoke_test.py against a running server: 22 of 22 checks"],
    ["Architecture and data flow are as described",
     "docs/ARCHITECTURE.md, docs/ERD.md, evidence/make_architecture_figure.py",
     "Every box in Figure 1 names a file that exists at that path"],
    ["Rules are enforced by the server, not the interface",
     "app/transitions.py, app/deps.py, app/schemas.py, database CHECK constraints",
     "backend/tests/test_transitions.py and test_security.py"],
    ["The interface offers only valid actions",
     "frontend/src/lib/transitions.js, components/EmailDetailPanel.jsx",
     "test_transitions.py asserts the mirror matches the Python table"],
    ["Problems were investigated, not just patched",
     "docs/BUG_LOG.md — 18 entries, each with a named regression test",
     "Appendix D; every entry cites the test that would catch its return"],
    ["No credential is published",
     "evidence/secret_scan.py, .gitignore, backend/.env.example",
     "The secrets job in CI fails the build on any finding"],
    ["The prototype is reproducible from the repository",
     "README.md, requirements.txt, package.json, database/schema.sql, seed data",
     "Follow README setup; CI performs the same steps from scratch"],
]

APPENDIX_B = [
    ["#", "Test", "Expected result", "Actual result", "Outcome"],
    ["B1", "Analyst signs in with valid credentials",
     "200 with a typed JWT; dashboard loads", "As expected (smoke check 2)", "Pass"],
    ["B2", "Sign in with a wrong password",
     "401 'Incorrect email or password', identical for an unknown address",
     "As expected (smoke check 3)", "Pass"],
    ["B3", "Protected route called with no token",
     "401 and no data returned", "As expected (smoke check 4)", "Pass"],
    ["B4", "Ingest a phishing sample",
     "Scored, level critical, auto-quarantined, audit row written",
     "Scored 80, quarantined, audited (smoke check 8)", "Pass"],
    ["B5", "Email detail explains its score",
     "The indicators that produced the score are returned",
     "6 named indicators (smoke check 7)", "Pass"],
    ["B6", "Blank sender and recipient submitted",
     "422 naming both fields", "As expected (smoke check 9)", "Pass"],
    ["B7", "501-character subject submitted",
     "422 at the API boundary, not a database error",
     "As expected (smoke check 10)", "Pass"],
    ["B8", "Quarantine a delivered email, then repeat the action",
     "First accepted; the repeat refused with 409",
     "200 then 409 'already quarantined' (checks 12-13)", "Pass"],
    ["B9", "Release an email that was never held",
     "409 naming the valid source states; status unchanged",
     "409, email stayed 'inbox' (smoke check 21)", "Pass"],
    ["B10", "Staff member lists email",
     "Only messages addressed to that user",
     "6 of 8 returned (smoke check 16)", "Pass"],
    ["B11", "Staff member opens the analyst audit log",
     "403 from the API regardless of the interface",
     "As expected (smoke check 17)", "Pass"],
    ["B12", "Release request with a 9-character reason",
     "422; the dialog stays open showing the server's message",
     "As expected (check 18, StaffPortal.test.jsx)", "Pass"],
    ["B13", "Second pending request for the same email",
     "409 and no second row created",
     "As expected (smoke check 19)", "Pass"],
    ["B14", "Analyst tries to raise a staff release request",
     "403 'Requires role: staff'", "As expected (smoke check 22)", "Pass"],
    ["B15", "Analyst approves a pending request",
     "Email released, review and audit rows written in one transaction",
     "All three updated (smoke check 20)", "Pass"],
    ["B16", "Token re-signed with a tampered role claim",
     "403, because the role is re-read from the database",
     "As expected (test_security.py)", "Pass"],
    ["B17", "Corrupt JSON written into score_reasons",
     "Detail still opens, with a placeholder reason",
     "As expected (test_integrity.py)", "Pass"],
    ["B18", "API made unreachable while the dashboard is open",
     "An explicit, retryable error with a request id",
     "As expected (Figure F8)", "Pass"],
]

APPENDIX_C = [
    ["Feature planned at proposal", "Status", "Where it is", "Note"],
    ["Role-based authentication for analyst, staff and admin", "Completed",
     "routers/auth.py, deps.py, security.py", "bcrypt hashes and expiring typed JWTs"],
    ["Explainable risk score with reasons", "Completed", "app/scoring.py",
     "Rule-based; stores score, level and named reasons"],
    ["Dashboard statistics and weekly distribution", "Completed",
     "routers/dashboard.py, pages/Dashboard.jsx", "Rendered from live queries"],
    ["Risk-sorted inbox and email detail", "Completed",
     "routers/emails.py, pages/Inbox.jsx", "Search and level filters included"],
    ["Analyst quarantine, release and phishing verdict", "Completed",
     "app/transitions.py, routers/emails.py", "State-guarded after BUG-17"],
    ["Staff release request with justification", "Completed",
     "routers/requests.py, pages/StaffPortal.jsx", "Staff-only, own mail, 10-character minimum"],
    ["Analyst or admin decision on a request", "Completed", "routers/requests.py",
     "Approval releases the email in the same transaction"],
    ["Audit trail of material actions", "Completed", "app/audit.py, routers/audit.py",
     "Append-only at application level"],
    ["PostgreSQL as the target database", "Completed", "database/schema.sql",
     "Verified on 16.6; SQLite retained as a fallback"],
    ["Automated tests and continuous integration", "Completed and expanded",
     "262 tests, four CI jobs", "Beyond the original plan, which named no CI"],
    ["DistilBERT text classifier", "Not implemented", "app/ml_model.py",
     "Documented placeholder; no running code path calls it"],
    ["Real SPF, DKIM and DMARC verification", "Not implemented",
     "simulated in app/scoring.py", "The synthetic samples carry no SMTP headers"],
    ["Automated browser-level end-to-end test", "Not implemented", "—",
     "The 22-check smoke workflow covers the API path instead"],
    ["Multi-factor authentication and token revocation", "Not implemented", "—",
     "Disclosed in Section 5 as a limitation"],
    ["Live mailbox integration and production deployment", "Excluded from scope", "—",
     "Excluded at proposal stage; local demonstration only"],
]

APPENDIX_D = [
    ["#", "Problem", "Fix", "Regression evidence"],
    ["BUG-17",
     "Any analyst action was accepted from any status. Only a repeated action was "
     "refused, so an email that had never been held could be released, writing a "
     "review row and an audit entry for a decision nobody made.",
     "app/transitions.py declares the valid source statuses once; the analyst route "
     "and the release-approval route both import it and answer 409 naming the states "
     "the action applies to.",
     "test_transitions.py (46 cases across every status and action, including one "
     "asserting a refused action writes neither a review nor an audit row); "
     "EmailDetailPanel.test.jsx (16 cases); smoke check 21."],
    ["BUG-18",
     "The ownership check tested the caller's role before comparing the recipient, so "
     "an analyst or administrator could raise a release request against any mailbox — "
     "recording a request the recipient never made.",
     "The endpoint is staff-only and the ownership comparison is unconditional. An "
     "analyst can already release an email directly, so no capability was lost.",
     "test_transitions.py role cases; smoke check 22 ('Requires role: staff')."],
    ["BUG-16",
     "Two concurrent duplicate release requests produced 503 'please try again'. The "
     "advice was impossible to act on, because the conflicting row is permanent until "
     "the request is decided.",
     "The integrity error is mapped to 409. The first fix identified the violation by "
     "index name, which PostgreSQL reports and SQLite does not; it now matches on the "
     "columns, so both engines behave the same.",
     "test_integrity.py concurrency case, run on both engines; the backend-postgres "
     "CI job repeats it on every push."],
    ["BUG-09",
     "One malformed JSON value in score_reasons made that message permanently "
     "unopenable with a 500, although the score, level and body were intact.",
     "The column is parsed defensively and a placeholder reason is substituted, so "
     "access to the record survives bad stored data.",
     "test_integrity.py corrupts a row deliberately, then asserts the detail endpoint "
     "still returns 200."],
    ["BUG-03",
     "SQLite silently accepted an over-long subject that PostgreSQL rejected, so the "
     "same input produced a 200 locally and a 500 on the target database.",
     "Pydantic bounds match the declared column widths, so over-long input is refused "
     "with 422 at the API boundary on either engine.",
     "test_validation.py boundary cases; smoke check 10; the PostgreSQL CI job."],
    ["BUG-01",
     "The pinned dependency versions could not be installed on Python 3.13 or later, "
     "because pydantic-core and psycopg2 publish wheels only for the interpreters that "
     "existed at that patch release.",
     "Compatible-release pins that allow patch updates.",
     "The CI matrix installs and runs the suite on Python 3.11, 3.12 and 3.13."],
]

AI_DECLARATION = (
    "Generative AI (Claude) was used extensively on this project, and this declaration "
    "describes that use rather than minimising it. It audited the repository against "
    "the assessment criteria, explained why the pinned dependency versions would not "
    "install on newer Python releases, drafted code changes and test cases, wrote the "
    "scripts that draw the figures in this report, and edited the wording of the report "
    "and the presentation. What it did not do is invent evidence. Every figure quoted "
    "in Section 5 and Appendix B is the recorded output of a command executed on this "
    "machine — the test counts, the coverage percentage, the smoke workflow and the "
    "PostgreSQL verification — and every screenshot and the walkthrough recording are "
    "captures of the running application. For each defect the process was to reproduce "
    "it with a probe test, apply a fix, then lock the behaviour in with a named "
    "regression test, which is why Appendix D can cite a specific test for every entry. "
    "I am responsible for the submitted code, its security, the citations and the "
    "explanation, and I can describe each change during the code review and the live "
    "demonstration."
)

# Screenshots reproduced full page, in the order they support the argument.
APPENDIX_F = [
    ("01-login.png",
     "Sign-in screen. The demo accounts are synthetic and use the reserved .local "
     "domain; no real credential appears anywhere in the submission."),
    ("03-analyst-dashboard.png",
     "Analyst dashboard rendered from live queries: counts by status, weekly threat "
     "distribution and the risk mix."),
    ("06-email-detail-explainable-score.png",
     "Explainable score in full: the six indicators that produced 100 out of 100, "
     "beside the simulated SPF, DKIM and DMARC results."),
    ("07-audit-log.png",
     "The append-only audit trail, recording actor, action, entity, detail and IP "
     "address for every material action."),
    ("09-staff-portal.png",
     "Staff portal. The signed-in staff member sees only mail addressed to them; the "
     "filtering is applied by the API, not the interface."),
    ("12-duplicate-request-blocked.png",
     "A second release request for the same email is refused. The rule is enforced by "
     "a partial unique index as well as by the route."),
    ("18-invalid-transition-blocked.png",
     "The transition guard in the interface: for a delivered email, Release is disabled "
     "while Quarantine and Confirm Phishing stay available."),
    ("16-error-state-api-unreachable.png",
     "Error handling when the API cannot be reached: an explicit, retryable message "
     "with a reference identifier, not an empty or permanently loading screen."),
]


def load_ci() -> tuple[dict, list[list[str]]]:
    """CI facts recorded by capture_ci_evidence.py, never typed in by hand."""
    path = HERE / "ci_evidence.json"
    if not path.exists():
        raise SystemExit(
            f"{path} is missing. Run: python evidence/capture_ci_evidence.py <tag>\n"
            "It refuses to write anything unless the latest run passed, which is what "
            "makes Appendix E evidence rather than an assertion."
        )
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec["conclusion"] != "success":
        raise SystemExit(f"recorded CI conclusion is {rec['conclusion']!r}, not success")

    what = {
        "Backend (pytest, Python 3.11)": "Installs from requirements-dev.txt and runs the 170 tests",
        "Backend (pytest, Python 3.12)": "The same suite, plus the coverage report artefact",
        "Backend (pytest, Python 3.13)": "The same suite; this is the regression guard for BUG-01",
        "Backend against PostgreSQL":
            "Starts a PostgreSQL 16 service, applies database/schema.sql with "
            "ON_ERROR_STOP, seeds into it and asserts 4 users and 8 emails, checks that "
            "five invalid statements are rejected, then runs the whole suite on it",
        "Secret scan":
            "Runs evidence/secret_scan.py over every tracked file and fails the build "
            "on any unacknowledged credential, key or token",
        "Frontend (vitest + build)": "npm ci, the 92 vitest tests, then a production build",
    }
    # The API returns jobs in completion order; present them in the order the
    # workflow declares them so the table reads as the pipeline, not a race result.
    order = list(what)
    rows = [["Job", "What it does", "Result"]]
    for job in sorted(rec["jobs"], key=lambda j: order.index(j["name"])
                      if j["name"] in order else len(order)):
        rows.append([job["name"], what.get(job["name"], "—"),
                     job["conclusion"].capitalize()])

    rec["intro"] = (
        f"Every push to main runs .github/workflows/ci.yml on GitHub-hosted runners, so "
        f"the repository carries evidence of building and passing that is independent of "
        f"this machine. Run #{rec['run_number']} on commit {rec['sha'][:7]}, the assessed "
        f"commit, completed with all {len(rec['jobs'])} jobs green."
    )
    rec["note"] = (
        f"The assessed version is the annotated tag {rec['tag']}, which points at commit "
        f"{rec['sha'][:7]} — the commit the run above tested, and the address in Figure E2. "
        f"The earlier v1.0, v1.1 and v1.2 final tags mark intermediate states; none was "
        f"moved, because rewriting a pushed tag would make the history misleading about what "
        f"was tested when. Any commit after the tag carries no application code: only "
        f"evidence captured from the tag — the two images on the next two pages and the JSON "
        f"record behind this table — which cannot be committed before the tag it documents "
        f"exists."
    )
    return rec, rows


def word_count(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    global CI, CI_TABLE
    CI, CI_TABLE = load_ci()
    if CI["tag"] != TAG:
        raise SystemExit(f"recorded tag {CI['tag']!r} does not match TAG {TAG!r} used "
                         "on the title page and in the references")
    doc = docx.Document(str(src))

    portrait_sectpr = copy.deepcopy(doc.sections[0]._sectPr)
    landscape_sectpr = copy.deepcopy(doc.sections[1]._sectPr)

    # -- 1. Title page ------------------------------------------------------
    title_table = doc.tables[1]
    for row in title_table.rows:
        label = row.cells[0].text.strip().upper()
        if label in TITLE_ROWS:
            cell = row.cells[1]
            set_text(cell.paragraphs[0], TITLE_ROWS[label])
        if label == "BODY WORD COUNT":
            word_row = row
    # The internal "IMPORTANT — before submitting" box is not part of a
    # submitted report.
    for t in list(doc.tables):
        if t.rows[0].cells[0].text.strip().upper().startswith("IMPORTANT"):
            delete(t)
            break
    set_text(find(doc, "Prepared 5 August"), "Prepared 12 August 2026")

    # -- 2. Body text -------------------------------------------------------
    counts: list[tuple[str, int]] = []
    for needle, text in BODY.items():
        p = find(doc, needle)
        set_text(p, text)
        p.paragraph_format.widow_control = True
        counts.append((needle[:34], word_count(text)))

    for needle, text in REFERENCES.items():
        set_text(find(doc, needle), text)

    # -- 3. Table 1: refresh, and move its caption above it -----------------
    old_cap = find(doc, "Table 1.")
    results_table = doc.tables[2]        # after the IMPORTANT box was removed
    delete(results_table)
    cap = add_caption(doc, old_cap, "Table 1. Verified results of the run on "
                                    "12 August 2026. Source: docs/TESTING.md.", above=True)
    delete(old_cap)
    build_table(doc, cap, TABLE1, [2.20, 1.90, 2.75])

    # -- 4. Figures 1-3, each on a landscape page ---------------------------
    # Figure 1 already occupies a landscape page; swap in the enlarged drawing.
    fig1 = [p for p in doc.paragraphs if p._p.findall(".//" + qn("w:drawing"))][0]
    for r in list(fig1.runs):
        r._r.getparent().remove(r._r)
    fig1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fig1.add_run().add_picture(str(FIGURES / "architecture.png"),
                               width=Inches(10.59), height=Inches(5.60))
    set_text(find(doc, "Figure 1."),
             "Figure 1. PhishGuard system architecture as implemented, in four layers "
             "with the trust boundary marked. Source: author, generated by "
             "evidence/make_architecture_figure.py from the code.")

    # Figure 2 (data model) goes immediately after Figure 1's landscape page, so
    # both design figures sit together with the section that cites them.
    fig1_caption = find(doc, "Figure 1.")
    anchor = fig1_caption
    while True:                      # the section-break paragraph after the caption
        nxt = anchor._p.getnext()
        if nxt is None or nxt.tag != qn("w:p"):
            break
        anchor = Paragraph(nxt, fig1_caption._parent)
        if anchor._p.find(qn("w:pPr") + "/" + qn("w:sectPr")) is not None:
            break

    # Both chain directly off a landscape break, so neither emits a portrait
    # terminator: that would put a blank page between the figures.
    tail = landscape_figure(
        doc, anchor, FIGURES / "erd-data-model.png",
        "Figure 2. Data model: five tables, their keys and relationships, and the "
        "integrity rules the database enforces rather than the application. Source: "
        "author, generated by evidence/make_erd_figure.py.",
        10.59, 6.35, portrait_sectpr, landscape_sectpr, after_landscape=True)

    tail = landscape_figure(
        doc, tail, FIGURES / "core-workflow.png",
        "Figure 3. The core workflow in four screens captured from the running "
        "application: triage, explain, challenge, decide. Full-page versions of these "
        "screens appear in Appendix F. Source: author's own captures.",
        10.59, 6.60, portrait_sectpr, landscape_sectpr, after_landscape=True)

    # -- 5. Appendices ------------------------------------------------------
    # A: refresh the evidence map in place.
    a_heading = find(doc, "Appendix A")
    set_text(a_heading, "Appendix A — Evidence map")
    keep_with_next(a_heading)
    for t in list(doc.tables):
        if t.rows[0].cells[0].text.strip().startswith("Report claim"):
            delete(t)
            break
    a_cap = add_caption(doc, a_heading,
                        "Table A1. Each claim in the report against the file that "
                        "supports it.", above=True)
    build_table(doc, a_cap, APPENDIX_A, [2.15, 2.40, 2.30])

    # Remove the old Appendix B (AI declaration, with its PERSONALISE box) and the
    # old Appendix C (an unfinished checklist). Both are replaced below.
    for t in list(doc.tables):
        if t.rows[0].cells[0].text.strip().upper().startswith("PERSONALISE"):
            delete(t)
            break
    old_ai = find(doc, "Generative AI (Claude) assisted")
    delete(old_ai)
    delete(find(doc, "Appendix B - AI-use declaration"))
    checklist_heading = find(doc, "Appendix C - Final manual verification")
    for p in list(doc.paragraphs):
        if p.text.strip().startswith(("☑", "☐")):
            delete(p)

    # The remaining heading becomes Appendix B, and the rest are built after it.
    b_heading = checklist_heading
    set_text(b_heading, "Appendix B — Representative functional tests")
    # Eighteen rows need a full page. Started mid-page the table spilled its last
    # row alone onto the next one, leaving a nearly empty page.
    b_heading.paragraph_format.page_break_before = True
    keep_with_next(b_heading)
    b_cap = add_caption(doc, b_heading,
                        "Table B1. Representative cases with expected and actual "
                        "results. Every row was executed; none is predicted.", above=True)
    b_table = build_table(doc, b_cap, APPENDIX_B, [0.42, 1.85, 2.00, 1.86, 0.72])

    c_heading = para_after(b_table, style="Heading 1")
    set_text(c_heading, "Appendix C — Planned versus completed features")
    c_heading.paragraph_format.page_break_before = True
    keep_with_next(c_heading)
    c_cap = add_caption(doc, c_heading,
                        "Table C1. What was planned at proposal against what the "
                        "submitted prototype does.", above=True)
    c_table = build_table(doc, c_cap, APPENDIX_C, [2.40, 1.25, 1.75, 1.45])

    d_heading = para_after(c_table, style="Heading 1")
    set_text(d_heading, "Appendix D — Problems, fixes and regression evidence")
    d_heading.paragraph_format.page_break_before = True
    keep_with_next(d_heading)
    d_cap = add_caption(doc, d_heading,
                        "Table D1. Extract from docs/BUG_LOG.md. Each fix names the "
                        "test that would catch the defect returning.", above=True)
    d_table = build_table(doc, d_cap, APPENDIX_D, [0.62, 2.05, 2.05, 2.13])

    e_heading = para_after(d_table, style="Heading 1")
    set_text(e_heading, "Appendix E — Continuous integration and release evidence")
    e_heading.paragraph_format.page_break_before = True
    keep_with_next(e_heading)

    e_intro = para_after(e_heading)
    set_text(e_intro, CI["intro"])
    e_cap = add_caption(doc, e_intro,
                        "Table E1. The jobs defined in .github/workflows/ci.yml — the "
                        "backend job runs as a three-version matrix — and the result of "
                        f"run #{CI['run_number']}.", above=True)
    e_table = build_table(doc, e_cap, CI_TABLE, [1.70, 3.90, 1.25])

    e_note = para_after(e_table)
    set_text(e_note, CI["note"])

    tail = landscape_figure(
        doc, e_note, SHOTS / CI["run_shot"],
        f"Figure E1. GitHub Actions run #{CI['run_number']} on commit "
        f"{CI['sha'][:7]}, every job green, on the public repository. "
        f"Source: {CI['run_url']}",
        10.59, 6.62, portrait_sectpr, landscape_sectpr)

    tail = landscape_figure(
        doc, tail, SHOTS / CI["tag_shot"],
        f"Figure E2. The assessed version, tag {TAG}, on the public repository. "
        f"Source: {TAG_URL}",
        10.59, 6.62, portrait_sectpr, landscape_sectpr, after_landscape=True)

    # -- Appendix F: full-page screenshots ----------------------------------
    # The heading and its note ride on the first landscape page rather than a
    # portrait page of their own, which is why that image is a little shorter.
    # One line of introduction, not a paragraph: every line here is height the
    # screenshot beneath it loses.
    f_pre = [
        ("Heading 1", "Appendix F — Full-page interface screenshots"),
        ("Normal",
         "Captured at 3200 x 2000 from the application running on PostgreSQL 16.6. The "
         "full set of 24 images and their generated index are in evidence/screenshots/."),
    ]

    anchor = tail
    for i, (name, caption) in enumerate(APPENDIX_F, 1):
        first = i == 1
        anchor = landscape_figure(
            doc, anchor, SHOTS / name,
            f"Figure F{i}. {caption} Source: evidence/screenshots/{name}.",
            9.45 if first else 10.59,
            5.91 if first else 6.62,
            portrait_sectpr, landscape_sectpr,
            after_landscape=True, pre=f_pre if first else None)

    # -- Appendix G: AI-use declaration -------------------------------------
    g_heading = para_after(anchor, style="Heading 1")
    set_text(g_heading, "Appendix G — Declaration on the use of generative AI")
    keep_with_next(g_heading)
    g_body = para_after(g_heading)
    set_text(g_body, AI_DECLARATION)

    # -- 6. Word count, recorded on the title page --------------------------
    total = sum(n for _, n in counts)
    set_text(word_row.cells[1].paragraphs[0],
             f"{total:,} words in the body (excluding the title page, tables, figure "
             f"captions, references and appendices)")

    doc.save(str(dst))

    print(f"Report written: {dst}")
    print(f"\nBody word count by paragraph (target 1,500-1,600):")
    for label, n in counts:
        print(f"  {n:>4}  {label}")
    print(f"  ----")
    print(f"  {total:>4}  TOTAL")
    if not 1500 <= total <= 1600:
        print(f"\n  WARNING: {total} is outside the 1,500-1,600 target range.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

