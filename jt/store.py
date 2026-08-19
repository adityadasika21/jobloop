"""Filesystem layer. Files under jobs/, learning/, profile/ ARE the state.

Everything here is deliberately boring: read YAML, write YAML, find the repo.
No cleverness, because both this machine and an unattended cloud routine call
into it and the results have to merge in git.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .model import job_slug, utcnow


class JobloopError(Exception):
    """User-facing error: printed without a traceback by cli.main()."""


# --------------------------------------------------------------------------- #
# Repo location
# --------------------------------------------------------------------------- #

def repo_root(start: Path | None = None) -> Path:
    """Walk up for the directory holding profile/master.yaml.

    Honours JOBLOOP_ROOT so the OpenClaw agent and cron jobs can call `jt`
    from anywhere without a cd.
    """
    env = os.environ.get("JOBLOOP_ROOT")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "profile" / "master.yaml").exists():
            return p
        raise JobloopError(f"JOBLOOP_ROOT={p} has no profile/master.yaml")

    cur = (start or Path.cwd()).resolve()
    for cand in [cur, *cur.parents]:
        if (cand / "profile" / "master.yaml").exists():
            return cand
    raise JobloopError(
        "not inside a jobloop repo (no profile/master.yaml found above "
        f"{cur}). Set JOBLOOP_ROOT or cd into the repo."
    )


def jobs_dir(root: Path) -> Path:
    return root / "jobs"


def job_dir(root: Path, slug: str) -> Path:
    d = jobs_dir(root) / slug
    if not d.exists():
        raise JobloopError(f"no such job: {slug}\nTry: jt status")
    return d


# Words that carry no identity. "ai" and "engineer" are in half these slugs,
# so matching on them makes everything ambiguous with everything.
_SLUG_STOPWORDS = frozenset("""
a an the and or of for at in on to with is was were be been being
i we my our you your it its this that these those there here
job jobs role roles position status update round done finished complete
completed waiting feedback interview interviewed call screen screening
question questions asked answered answer fine good bad well overall
""".split())


def _slug_tokens(s: str) -> list[str]:
    import re
    return [t for t in re.split(r"[^a-z0-9]+", str(s).lower()) if t]


def _needle_tokens(needle: str) -> list[str]:
    """Tokens worth matching on, plus adjacent pairs glued together.

    The glue matters: "auric ai" has to reach the slug `...-auricai-...`, and
    a person typing a company name does not know whether it was slugified as
    one word or two.
    """
    toks = [t for t in _slug_tokens(needle) if t not in _SLUG_STOPWORDS]
    joined = [a + b for a, b in zip(toks, toks[1:])]
    return toks + joined


def _token_match(needle_tok: str, job_toks: set[str]) -> bool:
    if needle_tok in job_toks:
        return True
    # Prefix either way, so "auric" reaches "auricai" and vice versa. Length 4
    # floor keeps "ml"/"nlp" from matching half the corpus.
    if len(needle_tok) >= 4:
        return any(t.startswith(needle_tok) or needle_tok.startswith(t)
                   for t in job_toks if len(t) >= 4)
    return False


def rank_jobs(root: Path, needle: str) -> list[tuple[str, float]]:
    """Every job scored against free text, best first.

    Rare words identify a job; common ones do not. So each matched token is
    weighted by how few jobs contain it — which is why a sentence naming
    "auricai" once outranks one saying "ai engineer" three times.
    """
    import math

    slugs = all_jobs(root)
    if not slugs:
        return []
    corpus: dict[str, set[str]] = {}
    for slug in slugs:
        job = load_job(root, slug)
        corpus[slug] = set(_slug_tokens(slug)) \
            | set(_slug_tokens(job.get("company", ""))) \
            | set(_slug_tokens(job.get("role", "")))

    n = len(slugs)
    df: dict[str, int] = {}
    for toks in corpus.values():
        for t in toks:
            df[t] = df.get(t, 0) + 1

    scored = []
    for slug, toks in corpus.items():
        score = 0.0
        for nt in set(_needle_tokens(needle)):
            if not _token_match(nt, toks):
                continue
            # A token in one job out of 24 is worth far more than one in 12.
            hits = min((df[t] for t in toks
                        if t == nt or (len(nt) >= 4 and len(t) >= 4
                                       and (t.startswith(nt) or nt.startswith(t)))),
                       default=n)
            score += math.log(1 + n / max(1, hits)) * (1.5 if len(nt) > 5 else 1.0)
        if score:
            scored.append((slug, round(score, 3)))
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored


def resolve_slug(root: Path, needle: str) -> str:
    """Accept a full slug, a substring, or a sentence that mentions the job.

    Typing the full 2026-08-18-company-role slug on a phone is miserable, and
    people do not type identifiers at all — they type "auric ai round 1 done,
    waiting for feedback". Both have to land on the same job.
    """
    jd = jobs_dir(root)
    if not jd.exists():
        raise JobloopError("no jobs yet")
    slugs = sorted(p.name for p in jd.iterdir() if p.is_dir())
    needle = (needle or "").strip()
    if not needle:
        raise JobloopError("no job given")
    if needle in slugs:
        return needle

    matches = [s for s in slugs if needle.lower() in s.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise JobloopError(
            f"{needle!r} is ambiguous, matches:\n  " + "\n  ".join(matches))

    ranked = rank_jobs(root, needle)
    if not ranked:
        raise JobloopError(f"no job matching {needle!r}")
    best, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    # Decisive means clearly ahead, not merely first. Guessing between two
    # jobs at the same company writes an interview onto the wrong timeline.
    if best_score >= runner_up * 1.4 or runner_up == 0.0:
        return best
    tied = [f"{s} ({sc})" for s, sc in ranked[:4]]
    raise JobloopError(
        f"{needle!r} is ambiguous, closest matches:\n  " + "\n  ".join(tied))


def all_jobs(root: Path) -> list[str]:
    jd = jobs_dir(root)
    if not jd.exists():
        return []
    return sorted(
        p.name for p in jd.iterdir()
        if p.is_dir() and (p / "job.yaml").exists()
    )


# --------------------------------------------------------------------------- #
# YAML IO
# --------------------------------------------------------------------------- #

def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise JobloopError(f"missing file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or (default if default is not None else {})


def write_yaml(path: Path, data: Any) -> None:
    """Atomic write with stable key order — keeps git diffs readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            data, fh,
            sort_keys=False, allow_unicode=True, default_flow_style=False,
            width=88,
        )
    tmp.replace(path)


def read_text(path: Path, default: str | None = None) -> str:
    if not path.exists():
        if default is not None:
            return default
        raise JobloopError(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #

def load_profile(root: Path) -> dict:
    prof = read_yaml(root / "profile" / "master.yaml")
    for key in ("identity", "evidence", "skill_groups"):
        if key not in prof:
            raise JobloopError(f"profile/master.yaml is missing '{key}'")
    return prof


def profile_sha(root: Path) -> str:
    """Short hash of the profile, stamped into every generated artifact.

    Lets you tell at a glance whether a resume was built from the current
    evidence base or a stale one.
    """
    raw = (root / "profile" / "master.yaml").read_bytes()
    return hashlib.sha256(raw).hexdigest()[:12]


def evidence_index(prof: dict) -> dict[str, dict]:
    return {e["id"]: e for e in prof.get("evidence", []) if e.get("id")}


def role_index(prof: dict) -> dict[str, dict]:
    return {r["id"]: r for r in prof.get("roles", []) if r.get("id")}


# --------------------------------------------------------------------------- #
# Job records
# --------------------------------------------------------------------------- #

def load_job(root: Path, slug: str) -> dict:
    return read_yaml(job_dir(root, slug) / "job.yaml")


def save_job(root: Path, slug: str, job: dict) -> None:
    write_yaml(jobs_dir(root) / slug / "job.yaml", job)


def append_event(root: Path, slug: str, kind: str, detail: str = "",
                 source: str = "manual", ref: str = "",
                 ts: str | None = None) -> bool:
    """Append to the job's timeline. Returns False if it was a duplicate.

    Deduping on (kind, ref) matters because the Gmail sync is re-run on a cron
    and would otherwise re-log the same thread every hour.
    """
    job = load_job(root, slug)
    events = job.setdefault("events", [])
    if ref:
        for e in events:
            if e.get("kind") == kind and e.get("ref") == ref:
                return False
    events.append({
        "ts": ts or utcnow(),
        "kind": kind,
        "detail": detail,
        "source": source,
        **({"ref": ref} if ref else {}),
    })
    save_job(root, slug, job)
    return True


def new_job_record(company: str, role: str, **kw) -> dict:
    """The canonical shape of job.yaml. Keys ordered for readable diffs."""
    now = utcnow()
    rec = {
        "company": company,
        "role": role,
        "url": kw.get("url", ""),
        "source": kw.get("source", "manual"),
        "location": kw.get("location", ""),
        "work_mode": kw.get("work_mode", ""),
        "status": kw.get("status", "queued"),
        "priority": kw.get("priority", ""),
        "fit_score": kw.get("fit_score"),
        "keyword_coverage": kw.get("keyword_coverage"),
        "stretch": bool(kw.get("stretch", False)),
        "posted_at": kw.get("posted_at", ""),
        "intake_at": kw.get("intake_at", now),
        "applied_at": kw.get("applied_at", ""),
        "closed_at": "",
        "outcome": "",
        "contacts": [],
        "notes": kw.get("notes", ""),
        "events": [],
    }
    return rec


# --------------------------------------------------------------------------- #
# Learning ledger
# --------------------------------------------------------------------------- #

def ledger_path(root: Path) -> Path:
    return root / "learning" / "ledger.yaml"


def load_ledger(root: Path) -> dict:
    return read_yaml(ledger_path(root), default={"weaknesses": []})


def save_ledger(root: Path, ledger: dict) -> None:
    write_yaml(ledger_path(root), ledger)


# --------------------------------------------------------------------------- #
# Git (best-effort: never fail a command because a push failed)
# --------------------------------------------------------------------------- #

def git(root: Path, *args: str, check: bool = False) -> tuple[int, str]:
    if not shutil.which("git"):
        return 127, "git not installed"
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    if check and proc.returncode != 0:
        raise JobloopError(f"git {' '.join(args)} failed:\n{out}")
    return proc.returncode, out


def commit_push(root: Path, message: str, push: bool = True) -> str:
    """Commit everything and optionally push. Returns a human status line.

    Intake from Discord runs unattended, so a failed push must be reported,
    not raised — the job is already safely on disk either way.
    """
    if (root / ".git").exists() is False:
        return "not a git repo; skipped commit"
    git(root, "add", "-A")
    code, _ = git(root, "diff", "--cached", "--quiet")
    if code == 0:
        return "nothing to commit"
    code, out = git(root, "commit", "-m", message)
    if code != 0:
        return f"commit failed: {out}"
    sha = git(root, "rev-parse", "--short", "HEAD")[1]
    if not push:
        return f"committed {sha} (not pushed)"
    code, out = git(root, "push")
    if code != 0:
        return f"committed {sha}; PUSH FAILED: {out.splitlines()[-1] if out else '?'}"
    return f"committed {sha} and pushed"


def head_sha(root: Path) -> str:
    code, out = git(root, "rev-parse", "--short", "HEAD")
    return out if code == 0 else ""
