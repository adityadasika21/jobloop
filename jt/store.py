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


def resolve_slug(root: Path, needle: str) -> str:
    """Accept a full slug, a directory name, or an unambiguous substring.

    Typing the full 2026-08-18-company-role slug on a phone is miserable, so
    `jt tailor joveo` works when it matches exactly one job.
    """
    jd = jobs_dir(root)
    if not jd.exists():
        raise JobloopError("no jobs yet")
    slugs = sorted(p.name for p in jd.iterdir() if p.is_dir())
    if needle in slugs:
        return needle
    matches = [s for s in slugs if needle.lower() in s.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise JobloopError(f"no job matching {needle!r}")
    raise JobloopError(
        f"{needle!r} is ambiguous, matches:\n  " + "\n  ".join(matches)
    )


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
