"""Work waiting for the routine.

GitHub Actions can run every deterministic thing in this repo — intake,
scaffolds, verification, LaTeX — but it cannot think, because there is no
ANTHROPIC_API_KEY here and there is not going to be one. The judgment runs on
Aditya's own machine, on his Claude Code subscription, on a timer.

So a Discord command that needs judgment does not do the judgment. It does the
deterministic half, drops a request here, and says so. The routine drains this
directory, does the thinking, answers in the channel, and deletes the request.

That split is the whole design:

    Discord ──▶ Actions ──▶ inbox/ ──▶ local routine ──▶ Discord
                (no judgment)          (all judgment)

Requests are files, not a database, for the same reason jobs are: two writers
(this machine and a workflow) and git in between.
"""
from __future__ import annotations

import re
from pathlib import Path

from .model import utcnow
from .store import JobloopError, read_yaml, write_yaml

KINDS = {
    "freetext": "raw text from /j — work out what he means and do it",
    "context":  "raw text from /ctx — turn it into an evidence unit",
    "message":  "a scaffolded message whose pitch still has to be written",
    "mail":     "sync Gmail into the job timelines, on request",
}


def inbox_dir(root: Path) -> Path:
    return root / "inbox"


def _slugify_id(kind: str, ts: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "", ts)[:15] + "-" + kind


def add(root: Path, kind: str, **fields) -> Path:
    if kind not in KINDS:
        raise JobloopError(f"unknown inbox kind {kind!r}; one of {', '.join(KINDS)}")
    ts = utcnow()
    rid = _slugify_id(kind, ts)
    rec = {
        "id": rid,
        "kind": kind,
        "requested_at": ts,
        "source": fields.pop("source", "discord"),
        "channel_id": fields.pop("channel_id", "") or "",
        **{k: v for k, v in fields.items() if v not in (None, "")},
    }
    path = inbox_dir(root) / f"{rid}.yaml"
    if path.exists():                      # same second, second request
        path = inbox_dir(root) / f"{rid}-2.yaml"
        rec["id"] = path.stem
    write_yaml(path, rec)
    return path


def pending(root: Path) -> list[dict]:
    d = inbox_dir(root)
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.yaml")):
        rec = read_yaml(p, default={})
        if rec:
            rec["_path"] = str(p.relative_to(root))
            out.append(rec)
    return out


def done(root: Path, rid: str) -> str:
    d = inbox_dir(root)
    hits = [p for p in d.glob("*.yaml") if p.stem == rid or rid in p.stem]
    if not hits:
        raise JobloopError(f"no inbox request matching {rid!r}")
    if len(hits) > 1:
        raise JobloopError(f"{rid!r} matches {[p.stem for p in hits]}")
    hits[0].unlink()
    return hits[0].stem
