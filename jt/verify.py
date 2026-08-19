"""Provenance enforcement.

This is the load-bearing module of the whole system. "Un-rejectable" is only
worth anything if every line survives an interviewer probing it, so tailoring
is constrained mechanically rather than by asking a model nicely:

  1. every bullet cites >=1 evidence unit that exists in master.yaml
  2. every number in a bullet appears in the cited units
  3. every skill/technology token in a bullet is present in the cited units
  4. skills listed in the skills section exist in the master inventory
  5. every emphasised (bolded) term is supported by the cited units too

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

# A capitalized word that merely starts a sentence is not a technology.
_SENTENCE_START_RE = re.compile(r"(?:^|[.!?;:\u2014\u2013-]\s+|\n\s*)$")


def _is_sentence_initial(text: str, pos: int) -> bool:
    return bool(_SENTENCE_START_RE.search(text[:pos]))


def _looks_technical(tok: str) -> bool:
    """True for camelCase, ALLCAPS and version-y tokens -- LangGraph, NER,
    XGrammar, g5.xlarge, GPT-4.1. These are always policed regardless of
    position, because that is where fabricated tooling actually shows up."""
    body = tok[1:]
    return (any(c.isupper() for c in body)      # internal caps
            or tok.isupper()                     # acronym
            or any(c.isdigit() for c in tok))    # version / instance type


# Generic words that pass the TECH_RE shape but carry no claim.
TECH_ALLOW = frozenset(norm_skill(w) for w in """
That This These Those There Their They It Its We Our My I He She
And But For With From Under Over Into Across While When Where Which
Also Then Than Now Both Each Every All Any Some Most More Less
Working Built Building Owned Owning Led Leading Used Using
Recently Currently Previously Additionally However Separately
Happy Would Open Thanks Hi Hope Came Wanted""".split()) | frozenset(
    norm_skill(w) for w in """
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


def profile_vocab(prof: dict) -> set[str]:
    """Terms that are true by virtue of the profile itself, not of any one
    evidence unit: real job titles, employers, schools, degrees.

    Without this, a headline saying "LLM Engineer" fails because no evidence
    unit's claim text contains the word "Engineer" -- even though it is his
    actual title. Seniority words stay policed: "Staff" or "Principal" are
    only allowed if a role really carries them.
    """
    vocab: set[str] = set()
    for r in prof.get("roles", []) or []:
        for field in ("title", "company", "location"):
            for tok in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*", str(r.get(field, ""))):
                vocab.add(norm_skill(tok))
    for e in prof.get("education", []) or []:
        for field in ("institution", "degree", "location"):
            for tok in re.findall(r"[A-Za-z][A-Za-z0-9+#.\-]*", str(e.get(field, ""))):
                vocab.add(norm_skill(tok))
    return vocab


def verify_bullets(bullets: list[dict], evidence: dict[str, dict],
                   label: str = "bullet", vocab: set[str] | None = None) -> list[str]:
    """Return a list of violation strings. Empty means clean."""
    problems: list[str] = []
    vocab = vocab or set()

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
            raw_tok = m.group(1)
            tok = norm_skill(raw_tok)
            if not tok or len(tok) < 3 or tok in TECH_ALLOW \
                    or tok in allowed_skills or tok in vocab:
                continue
            if tok in norm_skill(hay):
                continue
            if not any(c.isupper() or c.isdigit() for c in raw_tok):
                continue          # only police proper-noun-ish tokens
            # A plain Capitalized word opening a sentence is grammar, not a
            # claim. Distinctly technical shapes stay policed everywhere.
            if not _looks_technical(raw_tok) \
                    and _is_sentence_initial(text, m.start()):
                continue
            problems.append(
                f"{where}: mentions {m.group(1)!r} which the cited evidence "
                f"{prov} does not support"
            )

        # (5) emphasis. Bold is a claim about what matters, so it is held to
        # the same bar: a model may not bold a term the evidence never says.
        flat = " ".join(hay.split()).lower()
        for term in b.get("emphasize", []) or []:
            if str(term).strip().lower() not in flat:
                problems.append(
                    f"{where}: emphasises {term!r}, which the cited evidence "
                    f"{prov} does not contain — bold is a claim too"
                )

        # (4) declared skills
        for s in b.get("skills", []) or []:
            if norm_skill(s) not in allowed_skills:
                problems.append(
                    f"{where}: declares skill {s!r} absent from cited evidence {prov}"
                )

    return problems


def verify_profile(prof: dict) -> list[str]:
    """Check master.yaml itself, not a job.

    An `emphasize` term that appears nowhere in its own unit can never legally
    bold anything — it is a typo that would fail silently, forever, by simply
    never matching. Cheap to catch here.
    """
    problems: list[str] = []
    for u in prof.get("evidence", []) or []:
        parts = [str(u.get("claim", "")), str(u.get("name", ""))]
        parts += [str(v) for v in (u.get("metrics") or {}).values()]
        parts += [str(k) for k in (u.get("keywords") or [])]
        parts += [str(k) for k in (u.get("stack") or [])]
        flat = " ".join(" ".join(parts).split()).lower()
        for term in u.get("emphasize", []) or []:
            if str(term).strip().lower() not in flat:
                problems.append(
                    f"profile[{u['id']}]: emphasize {term!r} appears nowhere in "
                    f"the unit — it can never match a bullet"
                )
    return problems


def verify_job(root: Path, slug: str) -> list[str]:
    """Verify a job's tailored.yaml. Returns violations."""
    prof = load_profile(root)
    evidence = evidence_index(prof)
    vocab = profile_vocab(prof)
    d = job_dir(root, slug)
    tpath = d / "tailored.yaml"
    if not tpath.exists():
        raise JobloopError(
            f"{slug} has no tailored.yaml yet — run `jt worksheet {slug}` and "
            f"have Claude fill it in"
        )
    tailored = read_yaml(tpath)
    problems: list[str] = verify_profile(prof)

    for role in tailored.get("experience", []) or []:
        rid = role.get("role_id", "?")
        problems += verify_bullets(
            role.get("bullets", []) or [], evidence,
            label=f"experience[{rid}]", vocab=vocab,
        )
    for proj in tailored.get("projects", []) or []:
        pid = proj.get("name", "?")
        problems += verify_bullets(
            proj.get("bullets", []) or [], evidence,
            label=f"project[{pid}]", vocab=vocab,
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
    if hl and tailored.get("headline_provenance"):
        problems += verify_bullets(
            [{"text": hl, "provenance": tailored["headline_provenance"]}],
            evidence, label="headline", vocab=vocab,
        )
    elif hl and hl != prof["identity"].get("headline"):
        problems.append(
            "headline: rewritten but has no `headline_provenance` — a headline "
            "is a claim like any other"
        )

    return problems


def verify_message(root: Path, slug: str, mtype: str = "referral") -> list[str]:
    """An outbound message's pitch is a claim surface too — same bar.

    A resume that oversells gets caught by an interviewer. A message that
    oversells gets the interview, which is strictly worse.
    """
    from .message import paths, resolve_type
    mtype = resolve_type(mtype)
    prof = load_profile(root)
    evidence = evidence_index(prof)
    rpath, _ = paths(root, slug, mtype)
    if not rpath.exists():
        raise JobloopError(
            f"{slug} has no {rpath.name} — run "
            f"`jt message {slug} --type {mtype} --scaffold`")
    data = read_yaml(rpath)
    return verify_bullets(
        [{"text": data.get("pitch", ""), "provenance": data.get("provenance") or []}],
        evidence, label=f"{mtype} pitch", vocab=profile_vocab(prof),
    )


def verify_referral(root: Path, slug: str) -> list[str]:
    return verify_message(root, slug, "referral")
