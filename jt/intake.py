"""JD intake — the entry point from Discord, and the only step that must work
with no model in the loop.

The OpenClaw agent on this machine runs a local qwen3.5:4b. It is not trusted
to extract fields; it only pipes the raw message here. So this module uses
heuristics, records what it is unsure about, and lets the cloud routine (real
Claude) correct company/role during `analyze`. Getting intake slightly wrong is
recoverable; losing the JD is not.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from pathlib import Path

from .model import job_slug, today, utcnow
from .store import (
    JobloopError, all_jobs, jobs_dir, load_job, new_job_record, save_job,
    write_text,
)

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

URL_RE = re.compile(r"https?://\S+")

# Boards that reliably refuse anonymous fetches. We don't pretend otherwise.
HOSTILE_HOSTS = ("linkedin.com", "glassdoor.", "indeed.", "ziprecruiter.")


def extract_url(text: str) -> str:
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(").,>\"'") if m else ""


def fetch_url(url: str, timeout: int = 20) -> tuple[str, str]:
    """Return (text, note). Never raises — a failed fetch still yields a job."""
    if any(h in url for h in HOSTILE_HOSTS):
        return "", (
            "host blocks anonymous fetch; paste the JD text into "
            "jd.md manually or re-post it to Discord as text"
        )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            raw = resp.read(2_000_000).decode(charset, "replace")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        return "", f"fetch failed: {type(exc).__name__}: {exc}"
    return html_to_text(raw), ""


def html_to_text(raw: str) -> str:
    """Crude but dependency-free. Good enough to keep the JD's words."""
    raw = re.sub(r"(?is)<(script|style|nav|footer|svg)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", raw)
    raw = re.sub(r"(?i)<li[^>]*>", "\n- ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


# --------------------------------------------------------------------------- #
# Field guessing
# --------------------------------------------------------------------------- #

ROLE_HINTS = [
    "engineer", "developer", "scientist", "architect", "researcher",
    "manager", "lead", "analyst", "specialist", "consultant", "intern",
]

_LABEL_RE = {
    "company": re.compile(r"(?im)^\s*(?:company|employer|organization)\s*[:\-]\s*(.+)$"),
    "role":    re.compile(r"(?im)^\s*(?:role|title|position|job\s*title)\s*[:\-]\s*(.+)$"),
    "location": re.compile(r"(?im)^\s*(?:location|based in|office)\s*[:\-]\s*(.+)$"),
}


def guess_fields(text: str, url: str) -> dict:
    """Heuristics only. Anything not found is left blank and flagged."""
    out = {"company": "", "role": "", "location": "", "work_mode": ""}

    for key, rx in _LABEL_RE.items():
        m = rx.search(text or "")
        if m:
            out[key] = m.group(1).strip().strip(".,;")[:80]

    # "<Role> at <Company>" — the most common phrasing in a shared posting.
    # Scanned line-by-line over the top of the document, because the title
    # line is what carries it and a document-wide regex picks up prose like
    # "...experience at scale" instead.
    if not out["role"] or not out["company"]:
        for line in [l.strip() for l in (text or "").splitlines() if l.strip()][:15]:
            m = re.match(r"(?i)^(.{5,70}?)\s+(?:at|@|[-|\u2013])\s+([\w .&\'\-]{2,40})$",
                         line)
            if not m:
                continue
            role_part, company_part = m.group(1).strip(), m.group(2).strip()
            if not any(h in role_part.lower() for h in ROLE_HINTS):
                continue
            # "(Remote)" / "[Hybrid]" ride along on the title; pull the work
            # mode out of it and drop it from the role name.
            paren = re.findall(r"[(\[]([^)\]]{2,20})[)\]]", role_part)
            role_part = re.sub(r"\s*[(\[][^)\]]{2,20}[)\]]", "", role_part).strip()
            for token in paren:
                t = token.strip().lower()
                if t in ("remote", "hybrid", "onsite", "on-site"):
                    out["work_mode"] = t.replace("on-site", "onsite")
            out["role"] = out["role"] or role_part.strip(" -\u2013|,")
            out["company"] = out["company"] or company_part.strip(" -\u2013|,.")
            break

    # Greenhouse/Lever URLs carry the company in the path.
    if not out["company"] and url:
        m = re.search(r"(?:greenhouse\.io|lever\.co|ashbyhq\.com)/([\w\-]+)", url)
        if m:
            out["company"] = m.group(1).replace("-", " ").title()

    # First heading-ish line that looks like a title.
    if not out["role"]:
        for line in (text or "").splitlines()[:40]:
            line = line.strip()
            if 6 <= len(line) <= 70 and any(h in line.lower() for h in ROLE_HINTS):
                out["role"] = line.strip(".,;:-")
                break

    low = (text or "").lower()
    if re.search(r"\bfully remote\b|\bremote[- ]first\b|\b100% remote\b", low):
        out["work_mode"] = "remote"
    elif "hybrid" in low:
        out["work_mode"] = "hybrid"
    elif re.search(r"\bon[- ]site\b|\bin[- ]office\b", low):
        out["work_mode"] = "onsite"
    elif "remote" in low:
        out["work_mode"] = "remote"

    return out


# --------------------------------------------------------------------------- #

def find_duplicate(root: Path, company: str, role: str, url: str) -> str | None:
    """Re-posting the same JD from a phone is easy; don't fan out duplicates."""
    from .model import slugify
    c, r = slugify(company), slugify(role)
    for slug in all_jobs(root):
        job = load_job(root, slug)
        if url and job.get("url") and job["url"].split("?")[0] == url.split("?")[0]:
            return slug
        if c and r and slugify(job.get("company", "")) == c \
                and slugify(job.get("role", "")) == r:
            return slug
    return None


def intake(root: Path, raw: str, *, source: str = "manual",
           company: str = "", role: str = "", url: str = "",
           priority: str = "", allow_dupe: bool = False) -> tuple[str, list[str]]:
    """Create a job directory from a raw Discord message / pasted JD.

    Returns (slug, notes-for-the-user).
    """
    raw = (raw or "").strip()
    if not raw and not url:
        raise JobloopError("nothing to ingest: give JD text or a URL")

    notes: list[str] = []
    url = url or extract_url(raw)

    # Body = the message minus the bare URL, or the fetched page.
    body = URL_RE.sub("", raw).strip() if url else raw
    if url and len(body) < 200:
        fetched, note = fetch_url(url)
        if note:
            notes.append(note)
        if len(fetched) > len(body):
            body = fetched

    if not body:
        body = f"(no JD text captured)\n\nURL: {url}\n"
        notes.append("JD body is empty — paste the description into jd.md")

    guessed = guess_fields(body, url)
    company = company or guessed["company"]
    role = role or guessed["role"]

    if not company:
        company = "unknown-company"
        notes.append("could not determine company — set it in job.yaml")
    if not role:
        role = "unknown-role"
        notes.append("could not determine role — set it in job.yaml")

    if not allow_dupe:
        dupe = find_duplicate(root, company, role, url)
        if dupe:
            return dupe, [f"already tracked as {dupe} (use --allow-dupe to force)"]

    slug = job_slug(company, role)
    d = jobs_dir(root) / slug
    # A directory with no job.yaml is a husk, not a real job -- git cannot
    # delete empty directories, so an interrupted run leaves them behind and
    # they must not push a genuine job onto a "-2" slug.
    if d.exists() and not (d / "job.yaml").exists():
        pass
    elif d.exists():
        n = 2
        while True:
            cand = jobs_dir(root) / f"{slug}-{n}"
            if not cand.exists() or not (cand / "job.yaml").exists():
                break
            n += 1
        slug = f"{slug}-{n}"
        d = jobs_dir(root) / slug

    rec = new_job_record(
        company, role, url=url, source=source, priority=priority,
        location=guessed["location"], work_mode=guessed["work_mode"],
    )
    (d / "interviews").mkdir(parents=True, exist_ok=True)
    write_text(d / "jd.md", f"# {role} — {company}\n\n"
                            f"{'Source: ' + url if url else ''}\n\n{body}\n")
    save_job(root, slug, rec)

    from .store import append_event
    append_event(root, slug, "intake",
                 detail=f"via {source}" + (f" — {url}" if url else ""),
                 source=source)
    return slug, notes
