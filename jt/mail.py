"""Gmail → job timeline.

The Gmail connector is an MCP tool only Claude can call, so this module never
talks to Gmail itself. Claude fetches threads and pipes them here as JSON;
this side does the deterministic part — matching a message to a tracked job,
classifying what it means, and deduping so an hourly cron doesn't re-log the
same thread forever.

Keeping the classification here rather than in the prompt means the same email
always produces the same event, which is what makes the pipeline auditable.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .model import slugify, utcnow
from .store import (
    JobloopError, all_jobs, append_event, load_job, save_job,
)

# Ordered: the first pattern that matches wins, most decisive first.
CLASSIFIERS: list[tuple[str, str, re.Pattern]] = [
    ("offer", "offer", re.compile(
        r"(?i)\b(offer letter|pleased to offer|extend(?:ing)? an offer|"
        r"compensation package)\b")),
    # "unfortunately"/"regret to inform" are the polite forms. Plenty of ATSes
    # send the blunt one instead — Persistent's subject is literally
    # "Application Rejected" over a body that only says "not the right fit",
    # which fell through to a generic email event and left the job sitting in
    # `applied`, counting as silent.
    ("rejected", "rejected", re.compile(
        r"(?i)\b(unfortunately|regret to inform|not (?:be )?moving forward|"
        r"decided (?:to (?:go|proceed)|not to)|will not be progressing|"
        r"other candidates|position has been filled|no longer under consideration|"
        r"application (?:was |has been )?rejected|not (?:the|a) right fit|"
        r"not been (?:selected|shortlisted)|unable to (?:move|take) (?:you )?forward)\b")),
    ("interview", "interview", re.compile(
        r"(?i)\b(schedule (?:an? )?(?:interview|call|chat)|interview invit|"
        r"technical (?:round|interview)|onsite|panel|book a time|calendly|"
        r"availability for (?:a )?(?:call|interview)|"
        r"(?:updates?|feedback) of your interview|your interview for)\b")),
    ("assessment", "screening", re.compile(
        r"(?i)\b(assessment|coding (?:test|challenge)|take[- ]home|hackerrank|"
        r"codility|karat|online test)\b")),
    # Ordered before "screen" deliberately: every application confirmation
    # contains the phrase "your application", so a looser screen pattern
    # tested first would swallow all of them and mislabel real applications.
    ("applied", "applied", re.compile(
        r"(?i)\b(application (?:has been )?(?:received|submitted)|"
        r"thank(?:s| you) for applying|thank(?:s| you) for your application|"
        r"we(?:'ve| have) (?:successfully )?received your application|"
        r"successfully submitted application|"
        r"your application is currently in queue|"
        r"thank you for your recent application|"
        r"received your application for)\b")),
    ("screen", "screening", re.compile(
        r"(?i)\b(recruiter|initial (?:call|screen)|quick chat|"
        r"reach(?:ed|ing) out (?:about|regarding)|"
        r"shortlisted|next steps in your)\b")),
]

NOISE = re.compile(
    r"(?i)(job alert|jobs? for you|recommended for you|newsletter|unsubscribe"
    r"|new jobs? matching|weekly digest)")


def classify(subject: str, body: str) -> tuple[str, str] | None:
    """Return (event_kind, implied_status) or None if it's noise."""
    text = f"{subject}\n{body}"
    if NOISE.search(subject or ""):
        return None
    for kind, status, rx in CLASSIFIERS:
        if rx.search(text):
            return kind, status
    return ("email", "")


def match_job(root: Path, msg: dict, jobs_cache: dict | None = None) -> str | None:
    """Match a message to a tracked job by company name or domain."""
    jobs = jobs_cache if jobs_cache is not None else {
        s: load_job(root, s) for s in all_jobs(root)
    }
    sender = (msg.get("from") or "").lower()
    subject = (msg.get("subject") or "").lower()
    body = (msg.get("body") or msg.get("snippet") or "").lower()
    hay = f"{sender} {subject} {body[:1500]}"

    best, best_score = None, 0
    for slug, job in jobs.items():
        company = (job.get("company") or "").lower().strip()
        if not company or company == "unknown-company":
            continue
        score = 0
        tokens = [t for t in re.split(r"[^a-z0-9]+", company) if len(t) > 2]
        if not tokens:
            continue
        # Sender domain is the strongest signal.
        domain = sender.split("@")[-1].split(">")[0] if "@" in sender else ""
        if domain and any(t in domain for t in tokens):
            score += 5
        if company in subject:
            score += 3
        elif all(t in hay for t in tokens):
            score += 2
        if score == 0:
            continue

        # Company alone is not identity. Aditya has applied to several roles at
        # the same employer (Eightfold: "ML Engineer, NLP" and "Senior Engineer,
        # Fullstack"), and attaching a Fullstack rejection to the NLP job would
        # silently corrupt both timelines. When the email names a role, it has
        # to agree with the tracked one; when it names none, company stands.
        email_role = guess_role(msg)
        if email_role:
            sim = _role_similarity(email_role, job.get("role") or "")
            if sim < 0.34:
                continue
            score += 2 if sim >= 0.6 else 1

        if score > best_score:
            best, best_score = slug, score
    return best if best_score >= 2 else None


_ROLE_FILLER = {"senior", "staff", "principal", "lead", "junior", "the", "and",
                "of", "at", "for", "iii", "ii", "iv", "i", "sr", "jr"}

# Job-function nouns that appear in nearly every title. Counting these as
# matches made "Senior Engineer, Fullstack" and "ML Engineer, NLP/AI" look 50%
# similar on the word "engineer" alone — enough to merge two unrelated
# applications at the same company.
_ROLE_GENERIC = {"engineer", "engineering", "developer", "scientist", "analyst",
                 "architect", "specialist", "consultant", "manager", "intern",
                 "role", "position", "software"}


def _role_similarity(a: str, b: str) -> float:
    """Overlap of the *distinctive* words in two role titles, 0..1."""
    def toks(x: str) -> set[str]:
        return {t for t in re.split(r"[^a-z0-9]+", (x or "").lower())
                if len(t) > 1 and t not in _ROLE_FILLER}

    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    da, db = ta - _ROLE_GENERIC, tb - _ROLE_GENERIC
    # Compare on what actually distinguishes the roles; only fall back to the
    # full token sets when one title is nothing but generic words.
    if da and db:
        return len(da & db) / min(len(da), len(db))
    return len(ta & tb) / min(len(ta), len(tb))


# Kinds that prove an application actually exists, and so justify creating a
# job record from the email alone. A generic "email" or a recruiter cold-reach
# does not — those would fill the tracker with things he never applied to.
AUTO_INTAKE_KINDS = {"applied", "rejected", "interview", "assessment", "offer"}


def ingest(root: Path, messages: list[dict], apply_status: bool = True,
           auto_intake: bool = False) -> dict:
    """Fold a batch of Gmail messages into job timelines."""
    from .model import STATUS_ORDER, status_rank

    jobs_cache = {s: load_job(root, s) for s in all_jobs(root)}
    result = {"matched": 0, "unmatched": [], "noise": 0,
              "events_added": 0, "status_changes": [], "created": []}

    for msg in messages:
        cls = classify(msg.get("subject", ""), msg.get("body") or msg.get("snippet", ""))
        if cls is None:
            result["noise"] += 1
            continue
        kind, implied = cls

        slug = msg.get("job_slug") or match_job(root, msg, jobs_cache)

        # Most applications are submitted on a careers page and never pass
        # through Discord — the confirmation email is the only record. Create
        # the job from it so the tracker reflects what is actually in flight.
        if not slug and auto_intake and kind in AUTO_INTAKE_KINDS:
            company = guess_company(msg)
            role = guess_role(msg) or "unspecified role"
            if company:
                slug = _create_from_email(root, msg, company, role, kind)
                jobs_cache[slug] = load_job(root, slug)
                result["created"].append(
                    {"slug": slug, "company": company, "role": role})

        if not slug:
            result["unmatched"].append({
                "from": msg.get("from"), "subject": msg.get("subject"),
                "thread_id": msg.get("thread_id"), "kind": kind,
            })
            continue

        result["matched"] += 1
        ref = msg.get("thread_id") or msg.get("id") or ""
        detail = f"{msg.get('subject','(no subject)')} — from {msg.get('from','?')}"
        added = append_event(root, slug, kind, detail=detail,
                             source=f"gmail:{ref}" if ref else "gmail",
                             ref=ref, ts=msg.get("date") or utcnow())
        if not added:
            continue
        result["events_added"] += 1
        jobs_cache[slug] = load_job(root, slug)

        if apply_status and implied:
            job = jobs_cache[slug]
            cur = job.get("status", "queued")
            # Never walk the pipeline backwards on a stray email; a rejection
            # after an interview is still a forward move.
            if status_rank(implied) > status_rank(cur):
                job["status"] = implied
                if implied in ("rejected", "offer"):
                    job["closed_at"] = msg.get("date") or utcnow()
                    job["outcome"] = implied
                if implied == "applied" and not job.get("applied_at"):
                    job["applied_at"] = msg.get("date") or utcnow()
                save_job(root, slug, job)
                jobs_cache[slug] = job
                result["status_changes"].append(
                    {"slug": slug, "from": cur, "to": implied})
    return result



# --------------------------------------------------------------------------- #
# Auto-intake: turn an untracked application email into a tracked job.
#
# Most applications never pass through Discord -- they get submitted on a
# careers page and the only record is the confirmation email. Without this,
# the tracker only ever knows about jobs posted deliberately, which is a small
# fraction of what is actually in flight.
# --------------------------------------------------------------------------- #

# The sender domain is the ATS vendor, not the employer, for all of these.
# Company has to come from the subject or body instead.
ATS_VENDORS = (
    "greenhouse-mail.io", "greenhouse.io", "ashbyhq.com", "hire.lever.co",
    "lever.co", "myworkday.com", "workday.com", "jobvite.com", "kekamail.com",
    "darwinbox.in", "darwinbox.com", "csod.com", "smartrecruiters.com",
    "icims.com", "successfactors.com", "taleo.net", "careerparcel.com",
    "zohorecruit.com", "freshteam.com", "recruitee.com", "teamtailor.com",
    "bamboohr.com", "workable.com", "breezy.hr", "jazzhr.com", "avature.net",
)

# Ordered most-specific first. Group 1 = company, group 2 = role when present.
# A company/role name ends at a clause boundary, not at end-of-string. These
# patterns run against email BODIES where the phrase sits mid-paragraph, so
# anchoring on $ silently failed ("...application to Sarvam. Your application
# is currently...") or over-captured ("Accenture. We have now filled that
# role"). END bounds every capture on punctuation or a following clause.
_END = r"(?=[.,;:!?\"')\]]|\s+(?:and|for|as|we|our|your|the|this|to|it|is|has|-|–|—)\b|$)"
# (?-i:...) keeps the capital-letter requirement even though the surrounding
# patterns are case-insensitive. Without the scoped flag, (?i) makes [A-Z]
# match anything and the capture swallows the rest of the sentence.
_CAP = r"(?-i:[A-Z])"
_NAME = r"(" + _CAP + r"[\w.&'-]*(?:[ ]" + _CAP + r"[\w.&'-]*){0,3})"

_COMPANY_PATTERNS = [
    re.compile(r"(?i)\bthank(?:s| you) for applying (?:to|at)\s+" + _NAME + _END),
    re.compile(r"(?i)\bthank(?:s| you) for your application to\s+" + _NAME + _END),
    re.compile(r"(?i)\byour application to\s+" + _NAME + _END),
    re.compile(r"(?i)\bapplying to\s+" + _NAME + r"\s+for the (?:role|position)"),
    re.compile(r"(?i)\bthank(?:s| you) for choosing\s+" + _NAME + _END),
    re.compile(r"(?i)\b(?:interest in|career at|joining)\s+(?:a career at\s+)?"
               + _NAME + _END),
    # "The Standard India: Update on your application"
    re.compile(r"^" + _NAME + r"\s*:\s*(?:update|news|regarding)\b"),
    re.compile(r"(?i)\bposition\b.{0,60}?\bat\s+" + _NAME + _END),
    re.compile(r"(?i)\brole of\b.{0,60}?\bat\s+" + _NAME + _END),
    re.compile(r"(?i)\bat\s+" + _NAME + _END),
]

# Roles are lowercase-tolerant (an ATS writes "AI / ML Engineer III").
_ROLE_END = (r"(?=\s+(?:at|for|through|with|as|and|role|position|is|was|has)\b"
             r"|[.,;:!?\"')\]]|$)")
_ROLE_BODY = r"([\w/&,.+ -]{4,60}?)"

_ROLE_PATTERNS = [
    re.compile(r"(?i)\bapplication for (?:the )?(?:position|post|role)\s*(?:of|-|:)?\s*"
               + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\bfor the (?:role|position) of\s+" + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\bapplying (?:for|to) (?:the )?" + _ROLE_BODY
               + r"\s+(?:position|role)\b"),
    re.compile(r"(?i)\b(?:time )?to apply for\s+(?:the )?" + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\byour (?:application|interview) (?:for|in) (?:the )?"
               + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\breceived your application for\s+(?:the )?" + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\bin queue for\s+(?:the )?" + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\bapplication for\s+(?:the )?" + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\bin the role of\s+" + _ROLE_BODY + _ROLE_END),
    re.compile(r"(?i)\bapplying (?:for|to) (?:the )?" + _ROLE_BODY
               + r"\s+(?:position|role)\b"),
    re.compile(r"(?i)\b(?:the\s+)?" + _ROLE_BODY + r"\s+(?:role|position)\b"),
]

_ROLE_NOISE = re.compile(
    r"(?i)^(?:your|the|a|an|this|that|our|we|us|it|application|position|role|job)\b"
    r"|\b(?:application|thank you|received|update|news)$")


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip(" \t-–—,.:;!\"'")
    return text


def guess_company(msg: dict) -> str:
    """Employer name from an ATS confirmation email."""
    sender = (msg.get("from") or "").lower()
    subject = _clean(msg.get("subject", ""))
    body = _clean((msg.get("body") or msg.get("snippet") or ""))[:600]

    domain = ""
    m = re.search(r"@([\w.-]+)", sender)
    if m:
        domain = m.group(1).lower()

    # A first-party domain is the most reliable signal available.
    if domain and not any(v in domain for v in ATS_VENDORS):
        host = domain.split(".")
        drop = {"careers", "career", "jobs", "hr", "mail", "email", "no-reply",
                "noreply", "recruiting", "talent", "www", "smtp", "notify"}
        parts = [h for h in host[:-1] if h not in drop]
        if parts:
            return parts[-1].replace("-", " ").title()

    for rx in _COMPANY_PATTERNS:
        for hay in (subject, body):
            m = rx.search(hay)
            if m:
                cand = _trim_company(m.group(1))
                if 2 <= len(cand) <= 40 and not cand.lower().startswith("your"):
                    return cand
    return ""


# Trailing clause words the capture drags in when a name runs to a boundary.
_TRAILING = {"for", "we", "our", "your", "the", "and", "is", "has", "while",
             "to", "it", "as", "at", "in", "you", "this", "that", "they",
             "thank", "thanks", "position", "role", "team", "careers", "inc",
             "application", "hi", "hello", "dear"}
# A sentence break is ". " before a capital -- but "Skit.ai" and "Node.js" are
# one name, so only split when the period is followed by whitespace.
_SENTENCE_SPLIT = re.compile(r"\.\s+")


def _trim_company(raw: str) -> str:
    """Cut a captured company name back to the name itself.

    The capture allows internal periods (Skit.ai) which means it also runs
    straight through a sentence break into the next clause -- "BRAHMA. We have
    received". Split on a real sentence boundary, then peel off trailing
    filler words.
    """
    cand = _clean(_SENTENCE_SPLIT.split(_clean(raw))[0])
    parts = cand.split()
    while parts and parts[-1].strip(".,!").lower() in _TRAILING:
        parts.pop()
    return _clean(" ".join(parts))


def guess_role(msg: dict) -> str:
    subject = _clean(msg.get("subject", ""))
    body = _clean((msg.get("body") or msg.get("snippet") or ""))[:600]
    for rx in _ROLE_PATTERNS:
        for hay in (subject, body):
            m = rx.search(hay)
            if m:
                cand = _clean(m.group(1))
                cand = re.sub(r"(?i)\s*\b(JR|REQ)[-\w]*\b", "", cand).strip()
                cand = re.sub(r"^\d[\w-]*\s+", "", cand)      # req numbers
                if 4 <= len(cand) <= 60 and not _ROLE_NOISE.search(cand):
                    return cand
    return ""


def _create_from_email(root: Path, msg: dict, company: str, role: str,
                       kind: str) -> str:
    """Create a job directory from an application email.

    Marked `source: email` and left without a JD — `jt worksheet` will say so.
    The point is that the job exists in the tracker at all; the JD can be
    added later by posting the link in Discord.
    """
    from .intake import intake as do_intake

    date = (msg.get("date") or utcnow())[:10]
    body = (
        f"{role} at {company}\n\n"
        f"(Created from an application email on {date}; no JD text captured.\n"
        f"Post the posting URL in Discord to attach the real JD.)\n\n"
        f"Subject: {msg.get('subject', '')}\n"
        f"From: {msg.get('from', '')}\n\n"
        f"{msg.get('body') or msg.get('snippet', '')}\n"
    )
    slug, _notes = do_intake(root, body, source="email",
                             company=company, role=role)
    job = load_job(root, slug)
    job["intake_at"] = msg.get("date") or utcnow()
    if kind != "applied":
        # The confirmation email was missed but a later one proves he applied.
        job["applied_at"] = msg.get("date") or utcnow()
    save_job(root, slug, job)
    return slug


def load_messages(source: str) -> list[dict]:
    raw = sys.stdin.read() if source == "-" else Path(source).read_text("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JobloopError(f"invalid JSON: {exc}")
    if isinstance(data, dict):
        data = data.get("messages") or data.get("threads") or [data]
    if not isinstance(data, list):
        raise JobloopError("expected a JSON array of messages")
    return data


def needs_reply(root: Path, days: int = 3) -> list[dict]:
    """Jobs whose last inbound email looks like it wants an answer from you."""
    import datetime as dt
    out = []
    for slug in all_jobs(root):
        job = load_job(root, slug)
        if job.get("status") in ("rejected", "withdrawn", "ghosted"):
            continue
        inbound = [e for e in job.get("events", []) or []
                   if e.get("kind") in ("interview", "assessment", "screen")
                   and str(e.get("source", "")).startswith("gmail")]
        if not inbound:
            continue
        last = max(inbound, key=lambda e: e.get("ts", ""))
        out.append({"slug": slug, "company": job.get("company"),
                    "role": job.get("role"), "kind": last["kind"],
                    "ts": last.get("ts"), "detail": last.get("detail", "")[:120]})
    out.sort(key=lambda r: r["ts"] or "", reverse=True)
    return out
