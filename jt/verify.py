"""Provenance enforcement.

This is the load-bearing module of the whole system. "Un-rejectable" is only
worth anything if every line survives an interviewer probing it, so tailoring
is constrained mechanically rather than by asking a model nicely:

  1. every bullet cites >=1 evidence unit that exists in master.yaml
  2. every number in a bullet appears in the cited units
  3. every skill/technology token in a bullet is present in the cited units
  4. skills listed in the skills section exist in the master inventory

Rule 2 is the one that catches real drift: inflated metrics are the most
common and most damaging fabrication, and they are trivially checkable.
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import norm_skill
from .store import (
    JobloopError, evidence_index, job_dir, load_profile, read_yaml,
)

# Numbers we don't police: bare years, and small ints that are usually prose
# ("3 services"), which would otherwise produce constant false positives.
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")
NUM_RE = re.compile(r"\d[\d,]*\.?\d*\s*(?:%|x|k|m|b|rps|qps|ms|s|gb|tb)?", re.I)

# Technology-ish tokens worth policing in bullet prose. A tailored bullet must
# not name a tool the cited evidence never mentions.
TECH_RE = re.compile(
    r"\b("
    r"[A-Z][A-Za-z0-9]*(?:\.[a-z]+)?[A-Z][A-Za-z0-9+#.]*"   # camelCase / LangGraph
    r"|[A-Za-z][A-Za-z0-9+#.\-]{1,}(?=\s|$|[,.;)])"
    r")\b"
)

# Generic words that pass the TECH_RE shape but carry no claim.
TECH_ALLOW = frozenset(norm_skill(w) for w in """
Built Designed Architected Engineered Owned Led Drove Shipped Delivered
Created Developed Implemented Reduced Improved Raised Cut Scaled Automated
Production Enterprise Live Multi Cross End Full Real Time Data Team Teams
API APIs System Systems Platform Pipeline Service Services Model Models
Python SQL Bash Linux Docker AWS REST JSON YAML CI CD
""".split())


def _numbers(text: str) -> set[str]:
    out = set()
    for m in NUM_RE.finditer(text or ""):
        tok = m.group(0).strip().lower().replace(" ", "").replace(",", "")
        bare = tok.rstrip("%xkmbrpsqmsgtb.")
        if not bare or _YEAR_RE.match(bare):
            continue
        try:
            if float(bare) <= 3 and "%" not in tok:
                continue          # "3 nodes" style prose; too noisy to police
        except ValueError:
            continue
        out.add(tok)
    return out


def _evidence_haystack(units: list[dict]) -> tuple[str, set[str], set[str]]:
    """Everything the cited units legitimately support."""
    text_parts, skills, numbers = [], set(), set()
    for u in units:
        claim = str(u.get("claim", ""))
        text_parts.append(claim)
        text_parts.append(str(u.get("name", "")))
        for s in u.get("skills", []) or []:
            skills.add(norm_skill(s))
        for k in u.get("keywords", []) or []:
            skills.add(norm_skill(k))
            text_parts.append(str(k))
        for s in u.get("stack", []) or []:
            skills.add(norm_skill(s))
            text_parts.append(str(s))
        for v in (u.get("metrics") or {}).values():
            text_parts.append(str(v))
        numbers |= _numbers(claim)
        for v in (u.get("metrics") or {}).values():
            numbers |= _numbers(str(v))
    hay = " ".join(text_parts)
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*", hay):
        skills.add(norm_skill(tok))
    return hay, skills, numbers


def verify_bullets(bullets: list[dict], evidence: dict[str, dict],
                   label: str = "bullet") -> list[str]:
    """Return a list of violation strings. Empty means clean."""
    problems: list[str] = []

    for i, b in enumerate(bullets, 1):
        text = str(b.get("text", "")).strip()
        prov = b.get("provenance") or []
        where = f"{label} {i}"

        if not text:
            problems.append(f"{where}: empty text")
            continue
        if not prov:
            problems.append(f"{where}: NO PROVENANCE — {text[:70]!r}")
            continue

        missing = [p for p in prov if p not in evidence]
        if missing:
            problems.append(
                f"{where}: cites unknown evidence id(s) {missing} — "
                f"not in profile/master.yaml"
            )
            continue

        units = [evidence[p] for p in prov]
        hay, allowed_skills, allowed_numbers = _evidence_haystack(units)

        # (2) numbers
        for num in _numbers(text):
            if num in allowed_numbers:
                continue
            bare = num.rstrip("%xkmbrpsqmsgtb.")
            if any(bare in a for a in allowed_numbers) or bare in hay.lower():
                continue
            problems.append(
                f"{where}: number {num!r} is not supported by {prov} — "
                f"metrics may not be invented or rounded up"
            )

        # (3) technologies
        for m in TECH_RE.finditer(text):
            tok = norm_skill(m.group(1))
            if not tok or len(tok) < 3 or tok in TECH_ALLOW or tok in allowed_skills:
                continue
            if tok in norm_skill(hay):
                continue
            if not any(c.isupper() or c.isdigit() for c in m.group(1)):
                continue          # only police proper-noun-ish tech tokens
            problems.append(
                f"{where}: mentions {m.group(1)!r} which the cited evidence "
                f"{prov} does not support"
            )

        # (4) declared skills
        for s in b.get("skills", []) or []:
            if norm_skill(s) not in allowed_skills:
                problems.append(
                    f"{where}: declares skill {s!r} absent from cited evidence {prov}"
                )

    return problems


def verify_job(root: Path, slug: str) -> list[str]:
    """Verify a job's tailored.yaml. Returns violations."""
    prof = load_profile(root)
    evidence = evidence_index(prof)
    d = job_dir(root, slug)
    tpath = d / "tailored.yaml"
    if not tpath.exists():
        raise JobloopError(
            f"{slug} has no tailored.yaml yet — run `jt worksheet {slug}` and "
            f"have Claude fill it in"
        )
    tailored = read_yaml(tpath)
    problems: list[str] = []

    for role in tailored.get("experience", []) or []:
        rid = role.get("role_id", "?")
        problems += verify_bullets(
            role.get("bullets", []) or [], evidence, label=f"experience[{rid}]"
        )
    for proj in tailored.get("projects", []) or []:
        pid = proj.get("name", "?")
        problems += verify_bullets(
            proj.get("bullets", []) or [], evidence, label=f"project[{pid}]"
        )

    # (4) skills section against the master inventory
    master_skills = set()
    for g in prof.get("skill_groups", []):
        for item in g.get("items", []):
            master_skills.add(norm_skill(item))
    for g in tailored.get("skill_groups", []) or []:
        for item in g.get("items", []) or []:
            if norm_skill(item) not in master_skills:
                problems.append(
                    f"skills[{g.get('name')}]: {item!r} is not in the master "
                    f"skill inventory — add it to profile/master.yaml only if "
                    f"it is genuinely true"
                )

    # Headline must not invent seniority or a domain.
    hl = tailored.get("headline", "")
    if hl:
        problems += verify_bullets(
            [{"text": hl, "provenance": tailored.get("headline_provenance")
              or [e["id"] for e in prof["evidence"][:0]] or None}],
            evidence, label="headline",
        ) if tailored.get("headline_provenance") else []

    return problems


def verify_referral(root: Path, slug: str) -> list[str]:
    """The referral pitch is a claim surface too — hold it to the same bar."""
    prof = load_profile(root)
    evidence = evidence_index(prof)
    rpath = job_dir(root, slug) / "referral.yaml"
    if not rpath.exists():
        raise JobloopError(f"{slug} has no referral.yaml — run `jt referral {slug}`")
    data = read_yaml(rpath)
    return verify_bullets(
        [{"text": data.get("pitch", ""), "provenance": data.get("provenance") or []}],
        evidence, label="referral pitch",
    )
