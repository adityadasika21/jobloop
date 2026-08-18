"""The learning loop: interview debriefs → weakness ledger → drills.

Design rule that keeps this honest: a weakness is opened by evidence and closed
only by later evidence. Severity escalates automatically on repeat occurrences,
so "this keeps coming up" is a fact in the data rather than a feeling. You
cannot mark something resolved just because you have read about it — `resolve`
requires a recovery event where the topic came up again and went well.
"""
from __future__ import annotations

from pathlib import Path

from .model import SEVERITIES, slugify, today, utcnow
from .store import (
    JobloopError, job_dir, load_ledger, read_yaml, save_ledger, write_text,
    write_yaml,
)


def _find(ledger: dict, wid: str) -> dict | None:
    return next((w for w in ledger.get("weaknesses", []) if w["id"] == wid), None)


def escalate(sev: str) -> str:
    i = SEVERITIES.index(sev) if sev in SEVERITIES else 2
    return SEVERITIES[max(0, i - 1)]


def add_weakness(root: Path, topic: str, *, category: str = "technical",
                 severity: str = "medium", job_slug: str = "",
                 round_: int | None = None, quote: str = "",
                 kind: str = "interview", notes: str = "") -> tuple[str, bool]:
    """Open a weakness, or record another occurrence of an existing one.

    Returns (weakness_id, was_new).
    """
    ledger = load_ledger(root)
    ledger.setdefault("weaknesses", [])
    wid = slugify(topic, 48)
    w = _find(ledger, wid)
    now = utcnow()
    ev = {"ts": now, "kind": kind, "job_slug": job_slug or None,
          "round": round_, "quote": quote, "recovered": False}

    if w is None:
        w = {
            "id": wid, "topic": topic, "category": category,
            "severity": severity, "status": "open", "occurrences": 1,
            "first_seen": now, "last_seen": now, "notes": notes,
            "evidence": [ev],
        }
        ledger["weaknesses"].append(w)
        save_ledger(root, ledger)
        return wid, True

    w["occurrences"] = int(w.get("occurrences", 1)) + 1
    w["last_seen"] = now
    w.setdefault("evidence", []).append(ev)
    # Recurrence is the signal that matters — a topic that has now cost you
    # twice is more urgent than whatever you felt about it the first time.
    if w["occurrences"] >= 2:
        w["severity"] = escalate(w.get("severity", "medium"))
    if w.get("status") == "resolved":
        w["status"] = "open"
        w["resolved_at"] = None
        w["resolution"] = (w.get("resolution") or "") + \
            f" [REOPENED {today()}: came up again]"
    if notes:
        w["notes"] = (w.get("notes", "") + "\n" + notes).strip()
    save_ledger(root, ledger)
    return wid, False


def record_recovery(root: Path, wid: str, job_slug: str, round_: int,
                    quote: str = "") -> None:
    ledger = load_ledger(root)
    w = _find(ledger, wid)
    if not w:
        raise JobloopError(f"no weakness {wid!r} in the ledger")
    w.setdefault("evidence", []).append({
        "ts": utcnow(), "kind": "interview", "job_slug": job_slug,
        "round": round_, "quote": quote, "recovered": True,
    })
    w["last_seen"] = utcnow()
    save_ledger(root, ledger)


def resolve(root: Path, wid: str, resolution: str, force: bool = False) -> None:
    """Close a weakness. Requires a recorded recovery unless forced."""
    ledger = load_ledger(root)
    w = _find(ledger, wid)
    if not w:
        raise JobloopError(f"no weakness {wid!r}")
    recovered = any(e.get("recovered") for e in w.get("evidence", []))
    if not recovered and not force:
        raise JobloopError(
            f"{wid} has no recovery evidence — it was never re-tested in a real "
            f"interview. Record one with `jt learn recovered {wid} <job> <round>`, "
            f"or close it anyway with --force if you're accepting the risk."
        )
    w["status"] = "resolved"
    w["resolved_at"] = utcnow()
    w["resolution"] = resolution
    save_ledger(root, ledger)


def set_status(root: Path, wid: str, status: str) -> None:
    ledger = load_ledger(root)
    w = _find(ledger, wid)
    if not w:
        raise JobloopError(f"no weakness {wid!r}")
    w["status"] = status
    save_ledger(root, ledger)


def open_weaknesses(root: Path) -> list[dict]:
    ledger = load_ledger(root)
    ws = [w for w in ledger.get("weaknesses", [])
          if w.get("status") in ("open", "practicing")]
    ws.sort(key=lambda w: (SEVERITIES.index(w.get("severity", "medium"))
                           if w.get("severity") in SEVERITIES else 2,
                           -int(w.get("occurrences", 1))))
    return ws


def save_interview(root: Path, slug: str, data: dict) -> Path:
    """Write jobs/<slug>/interviews/round-N.yaml."""
    rnd = int(data.get("round", 1))
    path = job_dir(root, slug) / "interviews" / f"round-{rnd}.yaml"
    data.setdefault("recorded_at", utcnow())
    write_yaml(path, data)
    return path


def next_round(root: Path, slug: str) -> int:
    d = job_dir(root, slug) / "interviews"
    if not d.exists():
        return 1
    rounds = [int(p.stem.split("-")[1]) for p in d.glob("round-*.yaml")
              if p.stem.split("-")[-1].isdigit()]
    return max(rounds, default=0) + 1


def drill_stub(root: Path, w: dict) -> Path:
    """Create a drill file for a weakness if one doesn't exist yet.

    Deliberately a stub with prompts rather than generated content — Claude
    fills it in with material specific to your actual evidence and the JDs
    you're targeting.
    """
    path = root / "learning" / "drills" / f"{w['id']}.md"
    if path.exists():
        return path
    ev = w.get("evidence", [])
    seen = "\n".join(
        f"- {e.get('ts','')[:10]} · {e.get('job_slug') or 'n/a'}"
        f" round {e.get('round') or '-'}: {e.get('quote','') or '(no quote)'}"
        for e in ev
    )
    write_text(path, f"""# Drill — {w['topic']}

**Severity:** {w.get('severity')} · **Occurrences:** {w.get('occurrences')} ·
**Status:** {w.get('status')} · **First seen:** {w.get('first_seen','')[:10]}

## Where this cost you

{seen or '- (no evidence recorded)'}

## The answer you should be able to give cold

<!-- Claude: write the 60-90 second spoken answer, grounded in real evidence
     units from profile/master.yaml. No invented projects. -->

## Follow-ups you must survive

<!-- Claude: 5 probing follow-ups an interviewer asks after that answer. -->

## What to actually build or read

<!-- Claude: concrete, smallest-useful actions. Prefer shipping something
     small over reading, so this can later become a real evidence unit. -->

## Done when

- [ ] Answered cold, out loud, without notes
- [ ] Survived the follow-ups above
- [ ] Came up in a real interview and went well
      → `jt learn recovered {w['id']} <job> <round>`
""")
    return path
