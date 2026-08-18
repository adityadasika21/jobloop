"""The screening gate.

Two jobs:

  * `rank_evidence` — given a JD, score every evidence unit by how well it
    answers it. This drives the tailoring worksheet, so Claude sees the best
    true material first instead of reaching for something adjacent.

  * `screen` — score the finished resume the way a screen actually works:
    keyword coverage, a requirement-by-requirement matrix, and a 6-second-scan
    checklist. Gaps are reported plainly. A gap is a learning-ledger candidate,
    never a licence to invent a bullet.
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import norm_skill, tokenize
from .store import (
    JobloopError, evidence_index, job_dir, load_job, load_profile, read_text,
    read_yaml,
)

# Lines in a JD that state a requirement.
REQ_LINE_RE = re.compile(
    r"(?im)^\s*(?:[-*•▪]|\d+[.)])\s*(.{12,300})$"
)
REQ_SECTION_RE = re.compile(
    r"(?i)(requirements|qualifications|what you.{0,12}(?:bring|have|ll need)|"
    r"who you are|must have|skills|experience|you should have|about you)"
)
NICE_RE = re.compile(r"(?i)\b(nice to have|preferred|bonus|plus|desirable)\b")
YEARS_RE = re.compile(r"(?i)(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?year")


def unit_tokens(u: dict) -> set[str]:
    parts = [str(u.get("claim", "")), str(u.get("name", ""))]
    parts += [str(x) for x in (u.get("skills") or [])]
    parts += [str(x) for x in (u.get("keywords") or [])]
    parts += [str(x) for x in (u.get("stack") or [])]
    return tokenize(" ".join(parts)) | {norm_skill(x) for x in (u.get("skills") or [])}


def rank_evidence(prof: dict, jd_text: str) -> list[tuple[dict, float, list[str]]]:
    """Score each evidence unit against the JD. Returns (unit, score, hits)."""
    jd_tok = tokenize(jd_text)
    strength_w = {"core": 1.15, "strong": 1.0, "supporting": 0.85}
    ranked = []
    for u in prof.get("evidence", []):
        utok = unit_tokens(u)
        hits = sorted(jd_tok & utok)
        if not utok:
            continue
        # Overlap normalized by the unit's own size, so a short unit that is
        # dead-on outranks a long one that merely brushes the JD.
        score = (len(hits) / (len(utok) ** 0.5)) * strength_w.get(
            u.get("strength", "strong"), 1.0
        )
        ranked.append((u, round(score, 3), hits))
    ranked.sort(key=lambda t: t[1], reverse=True)
    return ranked


def extract_requirements(jd_text: str) -> list[dict]:
    """Pull requirement bullets out of a JD, flagging required vs nice-to-have."""
    lines = jd_text.splitlines()
    reqs: list[dict] = []
    in_nice = False
    for i, line in enumerate(lines):
        if REQ_SECTION_RE.search(line) and len(line) < 120:
            in_nice = bool(NICE_RE.search(line))
            continue
        if NICE_RE.search(line) and len(line) < 120:
            in_nice = True
            continue
        m = REQ_LINE_RE.match(line)
        if not m:
            continue
        text = m.group(1).strip()
        if len(text) < 12 or text.endswith(":"):
            continue
        reqs.append({
            "text": text,
            "kind": "nice_to_have" if (in_nice or NICE_RE.search(text)) else "required",
        })
    # Dedupe, cap — long JDs otherwise produce an unreadable matrix.
    seen, out = set(), []
    for r in reqs:
        key = r["text"].lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out[:40]


def match_requirement(req_text: str, prof: dict,
                      threshold_full: int = 2) -> dict:
    """Classify one requirement as met / partial / gap against the evidence."""
    rtok = tokenize(req_text)
    best, best_hits, best_score = None, [], 0.0
    for u in prof.get("evidence", []):
        hits = sorted(rtok & unit_tokens(u))
        if len(hits) > best_score:
            best, best_hits, best_score = u, hits, len(hits)

    gaps = {g["topic"]: g for g in prof.get("known_gaps", [])}
    named_gap = next(
        (g for t, g in gaps.items()
         if norm_skill(t).replace("-", " ") in req_text.lower()
         or t.replace("-", " ") in req_text.lower()),
        None,
    )

    if named_gap:
        status = "gap"
    elif best_score >= threshold_full:
        status = "met"
    elif best_score >= 1:
        status = "partial"
    else:
        status = "gap"

    return {
        "requirement": req_text,
        "status": status,
        "evidence": best["id"] if (best and status != "gap") else None,
        "matched_terms": best_hits[:8],
        "known_gap": named_gap["topic"] if named_gap else None,
        "gap_note": named_gap["note"] if named_gap else None,
    }


def years_required(jd_text: str) -> int | None:
    nums = [int(m.group(1)) for m in YEARS_RE.finditer(jd_text)]
    return max(nums) if nums else None


def screen(root: Path, slug: str) -> dict:
    """Score the tailored resume against the JD. Returns the report dict."""
    prof = load_profile(root)
    d = job_dir(root, slug)
    jd_text = read_text(d / "jd.md")
    tailored = read_yaml(d / "tailored.yaml", default={})
    if not tailored:
        raise JobloopError(f"{slug}: no tailored.yaml — nothing to screen")

    # ---- keyword coverage -------------------------------------------------
    resume_text = " ".join(
        [tailored.get("headline", "")]
        + [b.get("text", "")
           for r in tailored.get("experience", []) or []
           for b in r.get("bullets", []) or []]
        + [b.get("text", "")
           for p in tailored.get("projects", []) or []
           for b in p.get("bullets", []) or []]
        + [i for g in tailored.get("skill_groups", []) or []
           for i in g.get("items", []) or []]
    )
    resume_tok = tokenize(resume_text)
    jd_tok = tokenize(jd_text)

    # Only score JD terms that look like signal: appear in the JD's requirement
    # lines, not boilerplate about culture and benefits.
    reqs = extract_requirements(jd_text)
    req_tok = tokenize(" ".join(r["text"] for r in reqs)) or jd_tok
    covered = sorted(req_tok & resume_tok)
    missing = sorted(req_tok - resume_tok)
    coverage = len(covered) / len(req_tok) if req_tok else 0.0

    # ---- requirement matrix ----------------------------------------------
    matrix = [match_requirement(r["text"], prof) | {"kind": r["kind"]}
              for r in reqs]
    req_only = [m for m in matrix if m["kind"] == "required"]
    met = sum(1 for m in req_only if m["status"] == "met")
    partial = sum(1 for m in req_only if m["status"] == "partial")
    gap = sum(1 for m in req_only if m["status"] == "gap")

    # ---- seniority reality check -----------------------------------------
    yrs = years_required(jd_text)
    identity = prof.get("identity", {})
    start = str(identity.get("experience_start", "2022-05"))
    from datetime import date
    sy, sm = (int(x) for x in start.split("-")[:2])
    have = round((date.today() - date(sy, sm, 1)).days / 365.25, 1)
    stretch = bool(yrs and yrs > have + 1.0)

    # ---- 6-second scan ----------------------------------------------------
    checks = [
        {"check": "Headline names the JD's own role language",
         "pass": bool(tailored.get("headline")) and
                 any(t in tokenize(tailored.get("headline", "")) for t in req_tok)},
        {"check": "Top experience bullet answers a required item",
         "pass": bool(req_only) and any(
             m["status"] == "met" for m in req_only[:5])},
        {"check": "Every bullet carries a metric or a concrete system",
         "pass": all(
             re.search(r"\d", b.get("text", "")) or len(b.get("text", "")) > 90
             for r in tailored.get("experience", []) or []
             for b in r.get("bullets", []) or [])},
        {"check": "Keyword coverage of stated requirements >= 60%",
         "pass": coverage >= 0.60},
        {"check": "No required item is an unacknowledged gap",
         "pass": gap == 0},
        {"check": "Fits one page (<= 14 experience bullets)",
         "pass": sum(len(r.get("bullets", []) or [])
                     for r in tailored.get("experience", []) or []) <= 14},
    ]

    # Fit: coverage is what a screen actually measures; the matrix is what a
    # human recruiter reads. Weight them together, then penalise stretch.
    fit = round(
        100 * (0.5 * coverage
               + 0.5 * ((met + 0.5 * partial) / len(req_only) if req_only else 0.6))
        - (12 if stretch else 0)
    )
    fit = max(0, min(100, fit))

    return {
        "slug": slug,
        "fit_score": fit,
        "keyword_coverage": round(coverage, 3),
        "covered_terms": covered,
        "missing_terms": [t for t in missing if len(t) > 2][:40],
        "requirements": matrix,
        "summary": {"required_total": len(req_only), "met": met,
                    "partial": partial, "gap": gap,
                    "nice_to_have": len(matrix) - len(req_only)},
        "seniority": {"years_required": yrs, "years_have": have,
                      "stretch": stretch},
        "scan_checks": checks,
        "passes_gate": all(c["pass"] for c in checks),
    }


def render_report(rep: dict, job: dict) -> str:
    """Human-readable screening report — this is what lands in Discord."""
    s = rep["summary"]
    sen = rep["seniority"]
    L = [
        f"# Screening report — {job.get('role')} @ {job.get('company')}",
        "",
        f"**Fit score: {rep['fit_score']}/100**  ·  "
        f"keyword coverage {rep['keyword_coverage']*100:.0f}%  ·  "
        f"gate: {'PASS' if rep['passes_gate'] else 'FAIL'}",
        "",
        f"Required items — met {s['met']} · partial {s['partial']} · gap {s['gap']} "
        f"(of {s['required_total']}); {s['nice_to_have']} nice-to-have.",
        "",
    ]
    if sen["years_required"]:
        verdict = ("STRETCH — applying over-level, be deliberate"
                   if sen["stretch"] else "within range")
        L += [f"Experience asked: {sen['years_required']}y · "
              f"actual: {sen['years_have']}y → {verdict}", ""]

    L += ["## 6-second scan", ""]
    for c in rep["scan_checks"]:
        L.append(f"- [{'x' if c['pass'] else ' '}] {c['check']}")
    L += ["", "## Requirement matrix", "",
          "| Requirement | Status | Evidence |", "|---|---|---|"]
    for m in rep["requirements"]:
        icon = {"met": "✅ met", "partial": "🟡 partial", "gap": "❌ gap"}[m["status"]]
        if m["kind"] == "nice_to_have":
            icon += " *(nice-to-have)*"
        ev = m["evidence"] or (f"_{m['gap_note']}_" if m["gap_note"] else "—")
        req = m["requirement"].replace("|", "\\|")[:140]
        L.append(f"| {req} | {icon} | {ev} |")

    gaps = [m for m in rep["requirements"]
            if m["status"] == "gap" and m["kind"] == "required"]
    if gaps:
        L += ["", "## Real gaps — do not paper over these", "",
              "These are the questions that will decide the screen. Answer them "
              "in the cover note or accept the risk knowingly; they are also "
              "learning-ledger candidates (`jt learn add`).", ""]
        for m in gaps:
            L.append(f"- **{m['requirement'][:160]}**"
                     + (f" — {m['gap_note']}" if m["gap_note"] else ""))

    if rep["missing_terms"]:
        L += ["", "## JD terms absent from the resume", "",
              "Only add one if it is genuinely true — otherwise it is a gap, "
              "not a keyword to stuff.", "",
              ", ".join(f"`{t}`" for t in rep["missing_terms"])]
    return "\n".join(L) + "\n"
