"""Shared vocabulary: statuses, slugs, normalization.

Kept dependency-free so every other module can import it.
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata

# Pipeline order. `jt status` sorts by this; `jt advance` refuses to move
# backwards without --force so a stray email can't demote a live process.
STATUS_ORDER = [
    "queued",      # JD received, nothing done yet
    "analyzed",    # JD parsed into analysis.yaml
    "ready",       # tailored + verified + screened, awaiting your submit
    "applied",
    "screening",   # recruiter contact
    "interview",
    "offer",
    "rejected",
    "withdrawn",
    "ghosted",
]

TERMINAL = {"rejected", "withdrawn", "offer", "ghosted"}

EVENT_KINDS = {
    "intake", "analyzed", "tailored", "verified", "screened", "applied",
    "email", "screen", "interview", "assessment", "referral",
    "offer", "rejected", "withdrawn", "ghosted", "note",
}

STAGES = {
    "recruiter_screen", "technical", "system_design", "coding",
    "hiring_manager", "onsite", "final", "take_home", "other",
}

SEVERITIES = ["critical", "high", "medium", "low"]

# Word-ish tokens we never count as JD "keywords" when scoring coverage.
# Generic JD prose. These inflate the coverage denominator without being
# anything an ATS actually scores, and chasing them pushes tailoring toward
# stuffing filler words instead of real skills.
STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or that the to
with will you your we our their they this these those must should can able
role team work working experience years year strong excellent good great
plus preferred required requirements responsibilities qualifications about
who what while across using use used help helps including etc via new
comfortable familiarity familiar least such own build building built builds
design designing designs ship shipping develop developing developer
looking join company companies world class fast paced growing scale scaling
opportunity opportunities benefits culture mission vision values equal
candidate candidates applicant apply application ideal successful
ability abilities skill skills knowledge understanding proficiency proficient
solid deep hands hands-on demonstrated proven track record
partner partners collaborate collaboration cross functional stakeholders
drive driving deliver delivering delivery own owning ownership end
quality best practices standards
adapt adaptable advancements agility bachelor capable cases challenges
changing closely communication complex computer concepts conduct continuous
degree ensure ensuring enable enabling latest thorough translate understand
various multiple relevant appropriate effective efficiently seamless robust
modern advanced business stakeholder partnering timely effectively
similar related relevant various multiple several
more most other others any all both each every
you'll we're it's don't
day days week weeks month months
please note position job posting
""".split())


def utcnow() -> str:
    """ISO-8601 UTC timestamp, second precision. One format everywhere."""
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return _dt.date.today().isoformat()


def slugify(text: str, maxlen: int = 60) -> str:
    """Lowercase kebab-case, ASCII only. Stable across machines."""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", " ", text).strip().lower()
    text = re.sub(r"[-\s_]+", "-", text)
    return text[:maxlen].strip("-")


def job_slug(company: str, role: str, date: str | None = None) -> str:
    """Directory name for a job: 2026-08-18-joveo-ai-llm-engineer."""
    return f"{date or today()}-{slugify(company, 24)}-{slugify(role, 32)}"


def tokenize(text: str) -> set[str]:
    """Normalized content tokens, used for keyword coverage on both sides."""
    words = re.findall(r"[a-z0-9][a-z0-9+#.\-]*", (text or "").lower())
    out = set()
    for w in words:
        w = w.strip(".-")
        if len(w) < 2 or w in STOPWORDS or w.isdigit():
            continue
        out.add(w)
    return out


def norm_skill(s: str) -> str:
    """Normalize a skill token so 'Tool/Function Calling' == 'tool-calling'-ish.

    Used by `jt verify` to compare a tailored bullet's declared skills against
    the skills of the evidence units it cites.
    """
    s = str(s).lower().strip()
    s = re.sub(r"[/(),]", " ", s)
    s = re.sub(r"[^\w\s.+#-]", "", s)
    s = re.sub(r"[\s_]+", "-", s.strip())
    return s.strip("-")


def status_rank(status: str) -> int:
    try:
        return STATUS_ORDER.index(status)
    except ValueError:
        return -1


# Light suffix stemmer used ONLY for keyword-coverage reporting, never for
# provenance checks. It separates "you never mention this concept" from "you
# wrote 'pipeline' and the JD wrote 'pipelines'" -- a distinction that decides
# whether the fix is a real gap or one word form. Strict (exact) coverage
# stays the gate, because plenty of ATS keyword matching is literal.
def stem(word: str) -> str:
    """Crude but predictable. Plural/gerund folding only.

    An earlier version stripped a blanket "es", which turned "pipelines" into
    "pipelin" while "pipeline" stayed whole -- so the two never matched and
    every plural looked like a missing keyword.
    """
    w = (word or "").lower()
    if len(w) <= 4:
        return w
    if w.endswith(("ches", "shes", "sses", "xes", "zes")) and len(w) > 6:
        return w[:-2]
    if w.endswith("ies") and len(w) > 5:
        return w[:-3] + "y"
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if w.endswith("ing") and len(w) > 6:
        base = w[:-3]
        # "tracing" -> "trace", "gating" -> "gate": restore the dropped e so
        # gerunds fold onto their base noun/verb.
        return base if base.endswith(("e", "l", "r", "n", "t", "d")) else base
    if w.endswith("ed") and len(w) > 5:
        return w[:-2]
    return w


def stems(tokens) -> set[str]:
    return {stem(t) for t in tokens}
