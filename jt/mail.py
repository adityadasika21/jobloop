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
    ("rejected", "rejected", re.compile(
        r"(?i)\b(unfortunately|regret to inform|not (?:be )?moving forward|"
        r"decided (?:to (?:go|proceed)|not to)|will not be progressing|"
        r"other candidates|position has been filled|no longer under consideration)\b")),
    ("interview", "interview", re.compile(
        r"(?i)\b(schedule (?:an? )?(?:interview|call|chat)|interview invit|"
        r"technical (?:round|interview)|onsite|panel|book a time|calendly|"
        r"availability for (?:a )?(?:call|interview))\b")),
    ("assessment", "screening", re.compile(
        r"(?i)\b(assessment|coding (?:test|challenge)|take[- ]home|hackerrank|"
        r"codility|karat|online test)\b")),
    ("screen", "screening", re.compile(
        r"(?i)\b(recruiter|initial (?:call|screen)|quick chat|"
        r"reach(?:ed|ing) out (?:about|regarding)|your (?:application|profile))\b")),
    ("applied", "applied", re.compile(
        r"(?i)\b(application (?:received|submitted)|thank you for applying|"
        r"we(?:'ve| have) received your application)\b")),
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
        role_tokens = [t for t in re.split(r"[^a-z0-9]+", (job.get("role") or "").lower())
                       if len(t) > 3]
        if role_tokens and sum(1 for t in role_tokens if t in hay) >= 2:
            score += 1
        if score > best_score:
            best, best_score = slug, score
    return best if best_score >= 2 else None


def ingest(root: Path, messages: list[dict], apply_status: bool = True) -> dict:
    """Fold a batch of Gmail messages into job timelines."""
    from .model import STATUS_ORDER, status_rank

    jobs_cache = {s: load_job(root, s) for s in all_jobs(root)}
    result = {"matched": 0, "unmatched": [], "noise": 0,
              "events_added": 0, "status_changes": []}

    for msg in messages:
        cls = classify(msg.get("subject", ""), msg.get("body") or msg.get("snippet", ""))
        if cls is None:
            result["noise"] += 1
            continue
        kind, implied = cls

        slug = msg.get("job_slug") or match_job(root, msg, jobs_cache)
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
