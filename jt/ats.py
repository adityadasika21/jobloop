"""ATS simulation — does the machine actually read the resume?

Keyword coverage measured against tailored.yaml is a lie: the applicant
tracking system never sees the YAML. It sees whatever its PDF text extractor
recovers, in whatever order, and then regex-hunts for contact details, section
headings, dates, and skills.

So this module works the way an ATS does — it compiles the PDF, extracts the
text back out, and audits THAT. Anything the extractor loses is treated as
absent from the resume, because to Workday/Taleo/Greenhouse it is.

Failure modes this is built to catch:
  * multi-column or table layouts that interleave lines out of reading order
  * contact details rendered as icons or trapped in headers/footers
  * hyperlinks whose anchor text hides the URL ("GitHub" -> URL lost)
  * ligatures/kerning that split words ("fi", "ffi") so keywords stop matching
  * non-standard section headings the parser can't map to its own schema
  * dates in formats the parser can't turn into an employment range
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .model import stem, stems, tokenize

# Headings ATS parsers reliably map to their internal schema. Anything else
# risks the whole block being dropped or filed as "additional information".
CANONICAL_SECTIONS = {
    "experience": ["experience", "work experience", "professional experience",
                   "employment", "employment history"],
    "education": ["education", "academic background"],
    "skills": ["skills", "technical skills", "core skills", "competencies"],
    "projects": ["projects", "personal projects", "selected projects"],
}
REQUIRED_SECTIONS = ["experience", "education", "skills"]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?){2,4}\d{2,4}")
URL_RE = re.compile(r"(?:https?://)?(?:www\.)?[\w-]+\.[a-z]{2,}(?:/[\w./-]*)?", re.I)

# "April 2025 – Present", "Aug. 2018 – May 2022", "05/2022 - 02/2025"
DATE_RANGE_RE = re.compile(
    r"(?i)((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z.]*\s+\d{4}"
    r"|\d{1,2}[/-]\d{4})"
    r"\s*(?:-{1,2}|–|—|to)\s*"
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z.]*\s+\d{4}"
    r"|\d{1,2}[/-]\d{4}|present|current)"
)

# Glyphs that mean an extractor hit something it couldn't map to a character.
BAD_GLYPHS = ["�", "\x00", "(cid:"]


def extract_text(pdf: Path, layout: bool = False) -> str:
    """Extract as an ATS would. Raw (reading-order) mode is the default,
    because that is what naive parsers use."""
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext not available (poppler-utils)")
    cmd = ["pdftotext"]
    if layout:
        cmd.append("-layout")
    cmd += [str(pdf), "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {proc.stderr.strip()}")
    return proc.stdout



def line_boxes(pdf: Path) -> list[tuple[int, float, float, float, float, str]]:
    """(page, xmin, ymin, xmax, ymax, text) for every line, via pdftotext -bbox."""
    proc = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return []
    out, page = [], 0
    for m in re.finditer(
        r'<page[^>]*>|<line xMin="([\d.]+)" yMin="([\d.]+)" '
        r'xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>',
        proc.stdout, re.S,
    ):
        if m.group(0).startswith("<page"):
            page += 1
            continue
        text = re.sub(r"<[^>]+>", "", m.group(5))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            out.append((page, float(m.group(1)), float(m.group(2)),
                        float(m.group(3)), float(m.group(4)), text))
    return out


def find_collisions(pdf: Path, tol: float = 0.40) -> list[tuple[str, str]]:
    """Lines that visually overlap each other.

    Text extraction happily recovers both of two overlapping lines, so every
    other check in this module passes while the PDF is unreadable to a human.
    Tightening the class leading caused exactly this twice during the build,
    which is why it is checked mechanically now.
    """
    boxes = line_boxes(pdf)
    hits = []
    for i, (p1, x1a, y1a, x1b, y1b, t1) in enumerate(boxes):
        for (p2, x2a, y2a, x2b, y2b, t2) in boxes[i + 1:i + 4]:
            if p1 != p2:
                continue
            v = min(y1b, y2b) - max(y1a, y2a)
            h = min(x1b, x2b) - max(x1a, x2a)
            if v <= 0 or h <= 0:
                continue
            # Ratios, not absolutes. Two halves of a tabular row (title left,
            # dates right) share a baseline and overlap vertically by a full
            # line height while never touching horizontally -- and a \Huge
            # name pads its glyph box into the line below without colliding.
            # A genuine collision overlaps substantially in BOTH axes.
            min_h = max(1.0, min(y1b - y1a, y2b - y2a))
            min_w = max(1.0, min(x1b - x1a, x2b - x2a))
            if (v / min_h) > tol and (h / min_w) > 0.2:
                hits.append((t1[:60], t2[:60]))
    return hits


def _find_sections(text: str) -> dict[str, str | None]:
    low = text.lower()
    found = {}
    for canon, variants in CANONICAL_SECTIONS.items():
        hit = None
        for v in variants:
            # Heading = the phrase alone on a line (allowing trailing spaces).
            if re.search(rf"(?m)^\s*{re.escape(v)}\s*$", low):
                hit = v
                break
        if hit is None:
            for v in variants:
                if re.search(rf"(?m)^\s*{re.escape(v)}\b", low):
                    hit = v + " (inline)"
                    break
        found[canon] = hit
    return found


def audit(pdf: Path, profile: dict, jd_text: str = "",
          tailored_text: str = "") -> dict:
    """Full ATS audit of a built PDF."""
    raw = extract_text(pdf, layout=False)
    laid = extract_text(pdf, layout=True)
    ident = profile.get("identity", {})
    findings: list[dict] = []

    def check(id_: str, ok: bool, severity: str, msg: str, fix: str = ""):
        findings.append({"id": id_, "pass": bool(ok), "severity": severity,
                         "detail": msg, "fix": fix})

    low_raw = raw.lower()

    # ---- 1. Did anything extract at all? ---------------------------------
    check("text-extractable", len(raw.strip()) > 400, "critical",
          f"{len(raw.strip())} chars recovered by the text extractor",
          "If near zero the PDF is an image — never export a resume as a scan.")

    # ---- 2. Contact block -------------------------------------------------
    name = str(ident.get("name", ""))
    first_last_ok = all(part.lower() in low_raw for part in name.split()[:2])
    check("name", first_last_ok, "critical",
          f"name {'found' if first_last_ok else 'NOT found'} in extracted text",
          "Name must be body text, not an image or a header/footer.")

    email = str(ident.get("email", ""))
    check("email", email.lower() in low_raw, "critical",
          f"email {'found' if email.lower() in low_raw else 'NOT found'}",
          "ATS rejects or blank-fills applications with no parseable email.")

    digits = re.sub(r"\D", "", str(ident.get("phone", "")))
    raw_digits = re.sub(r"\D", "", raw)
    check("phone", digits[-10:] in raw_digits if digits else False, "high",
          "phone digits recovered" if digits[-10:] in raw_digits
          else "phone NOT recoverable from extracted text",
          "Keep the number as plain text; icons and ligatures break it.")

    # ---- 3. Links ---------------------------------------------------------
    # Two legitimate forms, and the check reports which one it actually found.
    # A bare URL survives extraction intact; anchor text ("GitHub") extracts as
    # the word and the address is lost, which is the cost of the nicer-looking
    # page. Aditya chose anchor knowingly, so anchor passes — but it passes
    # loudly, naming what a parser will not recover.
    labels = ident.get("link_labels") or {}
    squashed = low_raw.replace(" ", "")
    for key, url in (ident.get("links") or {}).items():
        bare = re.sub(r"^https?://(www\.)?", "", str(url)).rstrip("/").lower()
        label = str(labels.get(key, key)).lower()
        has_url = bare in squashed
        has_anchor = bool(label) and label in low_raw
        if has_url:
            detail = f"{key} URL present as text ({bare})"
        elif has_anchor:
            detail = (f"{key} present as anchor text ({label!r}) — the URL "
                      f"{bare} is NOT recoverable by a text extractor")
        else:
            detail = f"{key} MISSING entirely ({bare})"
        check(f"link-{key}", has_url or has_anchor, "medium", detail,
              "Neither the URL nor its anchor text survived extraction — the "
              "link is invisible to a parser and to anyone pasting the text.")

    # ---- 4. Sections ------------------------------------------------------
    sections = _find_sections(raw)
    for canon in REQUIRED_SECTIONS:
        hit = sections.get(canon)
        check(f"section-{canon}", hit is not None, "high",
              f"'{canon}' section {'recognised as ' + repr(hit) if hit else 'NOT recognised'}",
              f"Use a standard heading: one of {CANONICAL_SECTIONS[canon][:3]}.")

    # ---- 5. Employment dates ---------------------------------------------
    ranges = DATE_RANGE_RE.findall(raw)
    n_roles = len(profile.get("roles", []))
    check("date-ranges", len(ranges) >= n_roles, "high",
          f"{len(ranges)} parseable date range(s) for {n_roles} role(s) "
          f"(+education)",
          "Use 'Month YYYY - Month YYYY'. Parsers that can't build an "
          "employment timeline often score the resume as junior.")

    # ---- 6. Reading order -------------------------------------------------
    # If raw and -layout extraction disagree badly on line content, the layout
    # is multi-column and the parser will interleave unrelated text.
    raw_lines = [l.strip() for l in raw.splitlines() if len(l.strip()) > 25]
    laid_lines = [l.strip() for l in laid.splitlines() if len(l.strip()) > 25]
    common = len(set(raw_lines) & set(laid_lines))
    order_ok = (common / max(1, min(len(raw_lines), len(laid_lines)))) > 0.7
    check("reading-order", order_ok, "high",
          f"{common}/{min(len(raw_lines), len(laid_lines))} long lines agree "
          f"between reading-order and layout extraction",
          "Disagreement means multi-column/table layout — flatten to one column.")

    # ---- 7. Glyph damage --------------------------------------------------
    bad = [g for g in BAD_GLYPHS if g in raw]
    check("glyphs", not bad, "critical",
          f"no undecodable glyphs" if not bad else f"found {bad}",
          "Font is not embedding a usable ToUnicode map; switch fonts.")

    # Template leakage. A Jinja/Python object that stringified into the PDF
    # ("<built-in method items ...>") looks fine to every other check here but
    # is instantly disqualifying to a human. Caught this exact bug in the
    # skills section during the first build, hence a hard check.
    leaks = [pat for pat in (
        "built-in method", "object at 0x", "Undefined", "<class ",
        "\\VAR{", "\\BLOCK{", "{{", "}}", "None None", "dict_items",
    ) if pat in raw]
    check("no-template-leakage", not leaks, "critical",
          "no template artifacts" if not leaks else f"LEAKED {leaks}",
          "A context key collided with a Python attribute (e.g. `items`) or a "
          "variable was undefined. Fix jt/render.py, don't patch the .tex.")

    # Split-word damage: ligatures dropping letters ("workflow" -> "work ow").
    suspicious = re.findall(r"(?<![\w-])[a-z]{1,3}\s(?:ow|nd|rm|lter|le)\b", low_raw)
    check("ligatures", len(suspicious) < 3, "high",
          f"{len(suspicious)} possible ligature splits" +
          (f" e.g. {suspicious[:3]}" if suspicious else ""),
          "fi/ffi/fl ligatures extracting as gaps break keyword matching.")

    # ---- 8. Content fidelity ---------------------------------------------
    if tailored_text:
        want = tokenize(tailored_text)
        got = tokenize(raw)
        lost = sorted(w for w in want - got if len(w) > 3)
        ratio = 1 - (len(lost) / max(1, len(want)))
        check("content-fidelity", ratio > 0.95, "high",
              f"{ratio*100:.1f}% of intended terms survived extraction"
              + (f"; lost e.g. {lost[:8]}" if lost else ""),
              "Terms lost in extraction are invisible to keyword matching.")

    # ---- 9. Keyword match ON THE EXTRACTED TEXT --------------------------
    kw = {}
    if jd_text:
        from .screen import extract_requirements
        reqs = extract_requirements(jd_text)
        req_tok = tokenize(" ".join(r["text"] for r in reqs)) or tokenize(jd_text)
        got = tokenize(raw)
        hit = sorted(req_tok & got)
        miss = sorted(req_tok - got)
        cov = len(hit) / len(req_tok) if req_tok else 0.0

        # Split the misses: concept absent entirely vs. present under a
        # different word form. Only the first kind is a real gap.
        got_stems = stems(got)
        form_only = sorted(m for m in miss if stem(m) in got_stems)
        real_miss = sorted(m for m in miss if stem(m) not in got_stems)
        loose = (len(req_tok) - len(real_miss)) / len(req_tok) if req_tok else 0.0

        kw = {"coverage": round(cov, 3), "loose_coverage": round(loose, 3),
              "matched": hit,
              "missing": [m for m in real_miss if len(m) > 2][:40],
              "wrong_form": [m for m in form_only if len(m) > 2][:20]}
        check("ats-keyword-coverage", cov >= 0.60, "high",
              f"{cov*100:.0f}% of JD requirement terms present in the "
              f"EXTRACTED text",
              "This is the number the ATS scores, not the one in tailored.yaml.")

    # ---- 10. Visual collisions -------------------------------------------
    collisions = find_collisions(pdf)
    check("no-overlap", not collisions, "critical",
          "no overlapping text" if not collisions
          else f"{len(collisions)} overlapping line pair(s), e.g. "
               f"{collisions[0][0]!r} over {collisions[0][1]!r}",
          "Negative \\vspace in resume.cls is colliding lines. Extraction "
          "still succeeds, so only this check catches it.")

    # ---- 11. Length -------------------------------------------------------
    pages = raw.count("\f") or 1
    check("page-count", pages <= 2, "medium", f"{pages} page(s)",
          "Two pages max; one is safest at this experience level.")

    crit = [f for f in findings if not f["pass"] and f["severity"] == "critical"]
    high = [f for f in findings if not f["pass"] and f["severity"] == "high"]
    return {
        "pdf": str(pdf),
        "passes": not crit and not high,
        "critical_failures": len(crit),
        "high_failures": len(high),
        "findings": findings,
        "keywords": kw,
        "extracted_chars": len(raw.strip()),
        "extracted_text": raw,
    }


def render_audit(rep: dict) -> str:
    icon = {True: "✅", False: "❌"}
    sev = {"critical": "CRITICAL", "high": "HIGH", "medium": "medium"}
    L = ["# ATS parse audit", "",
         f"**{'PASS' if rep['passes'] else 'FAIL'}** — "
         f"{rep['critical_failures']} critical, {rep['high_failures']} high · "
         f"{rep['extracted_chars']} chars extracted", ""]
    if rep.get("keywords"):
        k = rep["keywords"]
        L += [f"Keyword coverage **on extracted text**: "
              f"{k['coverage']*100:.0f}% exact"
              + (f" · {k.get('loose_coverage', 0)*100:.0f}% allowing word-form "
                 f"variants" if k.get("loose_coverage") else ""), ""]
    L += ["| | Check | Result |", "|---|---|---|"]
    for f in rep["findings"]:
        tag = "" if f["pass"] else f" _({sev[f['severity']]})_"
        L.append(f"| {icon[f['pass']]} | `{f['id']}`{tag} | {f['detail']} |")
    fails = [f for f in rep["findings"] if not f["pass"] and f["fix"]]
    if fails:
        L += ["", "## Fixes", ""]
        for f in fails:
            L.append(f"- **{f['id']}** — {f['fix']}")
    k = rep.get("keywords", {})
    if k.get("wrong_form"):
        L += ["", "## Present, but in the wrong word form", "",
              "The concept is on the resume under a different inflection. "
              "Literal ATS matching misses these, so adopt the JD's exact "
              "wording where the claim stays true.", "",
              ", ".join(f"`{t}`" for t in k["wrong_form"])]
    if k.get("missing"):
        L += ["", "## JD terms genuinely absent", "",
              "Add only what is true; the rest are gaps for the ledger.", "",
              ", ".join(f"`{t}`" for t in k["missing"])]
    return "\n".join(L) + "\n"
