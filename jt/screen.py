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
# Responsibilities are neither hard requirements nor nice-to-haves: they say
# what the job IS. They belong in keyword coverage but must not be counted as
# unmet qualifications, which would make every fit score look worse than it is.
RESP_RE = re.compile(
    r"(?i)^(what you.{0,6}(?:will |ll )?do|responsibilities|the role|"
    r"in this role|day to day|what the job)")
YEARS_RE = re.compile(r"(?i)(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?year")


def unit_tokens(u: dict, role_domains: dict[str, list] | None = None) -> set[str]:
    """Tokens an evidence unit legitimately answers to.

    A unit inherits its role's domain: work done at an HR-tech company IS
    HR-tech experience, even when the bullet never says the word. Without
    this, "experience in the recruitment domain" scored as a gap for someone
    whose day job is building a hiring-integrity platform.
    """
    parts = [str(u.get("claim", "")), str(u.get("name", ""))]
    parts += [str(x) for x in (u.get("skills") or [])]
    parts += [str(x) for x in (u.get("keywords") or [])]
    parts += [str(x) for x in (u.get("stack") or [])]
    if role_domains and u.get("role") in role_domains:
        parts += [str(d).replace("-", " ") for d in role_domains[u["role"]]]
    return tokenize(" ".join(parts)) | {norm_skill(x) for x in (u.get("skills") or [])}


def domain_map(prof: dict) -> dict[str, list]:
    return {r["id"]: (r.get("domain") or []) for r in prof.get("roles", [])}


def rank_evidence(prof: dict, jd_text: str) -> list[tuple[dict, float, list[str]]]:
    """Score each evidence unit against the JD. Returns (unit, score, hits)."""
    jd_tok = tokenize(jd_text)
    strength_w = {"core": 1.15, "strong": 1.0, "supporting": 0.85}
    doms = domain_map(prof)
    ranked = []
    for u in prof.get("evidence", []):
        utok = unit_tokens(u, doms)
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
    in_nice = in_resp = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        is_bullet = bool(REQ_LINE_RE.match(line))
        # A heading is a SHORT, non-bullet line. Without the bullet guard,
        # "- 3+ years of software engineering experience..." matches
        # REQ_SECTION_RE on the word "experience" and the entire requirements
        # block gets skipped as if it were a heading.
        is_heading = (not is_bullet and len(stripped) < 60
                      and stripped.endswith((":", "")) is not None)
        if is_heading and REQ_SECTION_RE.search(stripped):
            in_nice, in_resp = bool(NICE_RE.search(stripped)), False
            continue
        if is_heading and NICE_RE.search(stripped):
            in_nice, in_resp = True, False
            continue
        if is_heading and RESP_RE.search(stripped):
            in_nice, in_resp = False, True
            continue
        m = REQ_LINE_RE.match(line)
        if not m:
            continue
        text = m.group(1).strip()
        if len(text) < 12 or text.endswith(":"):
            continue
        # Absorb indented wrapped continuation lines so a requirement isn't
        # truncated mid-sentence ("...at least 2 years building" / "production
        # machine learning or LLM-powered systems").
        for nxt in lines[i + 1:i + 4]:
            if not nxt.strip() or REQ_LINE_RE.match(nxt):
                break
            if nxt.startswith(("  ", "\t")) and len(nxt.strip()) > 3:
                text += " " + nxt.strip()
            else:
                break
        reqs.append({
            "text": text,
            "kind": ("nice_to_have" if (in_nice or NICE_RE.search(text))
                     else "responsibility" if in_resp else "required"),
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
    doms = domain_map(prof)
    best, best_hits, best_score = None, [], 0.0
    for u in prof.get("evidence", []):
        hits = sorted(rtok & unit_tokens(u, doms))
        if len(hits) > best_score:
            best, best_hits, best_score = u, hits, len(hits)

    gaps = {g["topic"]: g for g in prof.get("known_gaps", [])}
    named_gap = next(
        (g for t, g in gaps.items()
         if norm_skill(t).replace("-", " ") in req_text.lower()
         or t.replace("-", " ") in req_text.lower()),
        None,
    )

    # Evidence decides the status; a named gap only downgrades it.
    # A requirement phrased as alternatives ("LangChain, LangGraph, or DSPy")
    # is MET when the evidence covers some of them, even though DSPy is a
    # known gap -- letting the gap term veto real evidence understated fit
    # badly and would push tailoring toward inventing the missing item.
    if best_score >= threshold_full:
        status = "met"
    elif best_score >= 1:
        status = "partial"
    else:
        status = "gap"
    if named_gap and status == "met":
        # Strong evidence stands, but the caveat is still worth carrying into
        # the report so it can be spoken to in an interview.
        pass
    elif named_gap and status == "partial":
        status = "partial"
    elif named_gap:
        status = "gap"

    return {
        "requirement": req_text,
        "status": status,
        "evidence": best["id"] if (best and status != "gap") else None,
        "caveat": (f"{named_gap['topic']}: {named_gap['note']}"
                   if named_gap and status == "met" else None),
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
                    "nice_to_have": sum(1 for m in matrix
                                        if m["kind"] == "nice_to_have"),
                    "responsibilities": sum(1 for m in matrix
                                            if m["kind"] == "responsibility")},
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
        elif m["kind"] == "responsibility":
            icon += " *(responsibility)*"
        ev = m["evidence"] or (f"_{m['gap_note']}_" if m["gap_note"] else "—")
        if m.get("caveat"):
            ev += f" ⚠️ _{m['caveat']}_"
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
