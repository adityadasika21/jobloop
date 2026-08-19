"""Adding a new true thing to the master profile.

This is the most dangerous write in the system. Every resume bullet and every
outbound message is generated ONLY from `profile/master.yaml`, and `jt verify`
trusts it absolutely — so a claim that gets in here is a claim Aditya will be
asked to defend in a room, months later, having forgotten he ever typed it
into Discord.

There is no human confirmation gate (his call, 2026-08-19). What there is
instead:

  * `source_note` and `added_at` on every unit written this way, so any claim
    can be traced back to the words that produced it
  * `probe` is REQUIRED and non-empty. It is the honesty lever the whole
    profile already runs on: if he can't answer the probe, the unit is written
    too strongly, and a unit with no probe is a unit nobody has stress-tested
  * `on_master: false` by default. New context is immediately available to
    tailoring but does not silently rewrite the one-page master resume, which
    is his own hand-written document
  * a text splice rather than a YAML round-trip, because dumping this file
    back through the parser would strip every comment in it, including the
    rules at the top that tell the next writer what a unit may claim
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from .model import utcnow
from .store import JobloopError, load_profile, read_yaml, write_yaml

SENTINEL = "  # <<< jt evidence add"
STRENGTHS = ("core", "strong", "supporting")
REQUIRED = ("id", "claim", "skills", "keywords", "strength", "probe")

DRAFT_FILE = "pending-evidence.yaml"


def draft_path(root: Path) -> Path:
    return root / "profile" / DRAFT_FILE


def draft(root: Path, text: str) -> Path:
    """Write the scaffold Claude fills in, with everything it needs to not
    guess: the raw words, the ids already taken, and the skill inventory."""
    prof = load_profile(root)
    out = {
        "_instructions": (
            "Turn `raw` into ONE atomic evidence unit — or several, if it "
            "genuinely contains several distinct facts. RULES: (1) `claim` is "
            "one true sentence in Aditya's voice, phrased as it would appear "
            "on a resume; (2) never state a number `raw` does not contain, and "
            "put every number in `metrics` verbatim so it stays quotable; "
            "(3) `skills` and `keywords` describe what was ACTUALLY done — "
            "keywords are JD-side synonyms for it, never aspirations; "
            "(4) `probe` is REQUIRED: the question an interviewer asks if this "
            "earns a screen pass. If he could not answer it, the claim is "
            "written too strongly — weaken the claim, don't soften the probe; "
            "(5) `strength`: core | strong | supporting; (6) set `role` to a "
            "role id below, or `kind: project` with `name` and `stack`. "
            "Then: jt evidence add profile/" + DRAFT_FILE
        ),
        "raw": text,
        "_existing_ids": [u["id"] for u in prof.get("evidence", [])],
        "_roles": [{"id": r["id"], "title": r["title"], "company": r["company"]}
                   for r in prof.get("roles", [])],
        "_skill_inventory": prof.get("skill_groups", []),
        "units": [{
            "id": "", "role": "", "claim": "", "skills": [], "metrics": {},
            "keywords": [], "strength": "strong", "emphasize": [], "probe": "",
        }],
    }
    path = draft_path(root)
    write_yaml(path, out)
    return path


def validate(prof: dict, unit: dict) -> list[str]:
    problems = []
    uid = str(unit.get("id") or "")
    for field in REQUIRED:
        v = unit.get(field)
        if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
            problems.append(f"{uid or '(no id)'}: `{field}` is required and empty")

    if uid and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", uid):
        problems.append(f"{uid}: id must be lowercase-kebab-case")
    if uid in {u["id"] for u in prof.get("evidence", [])}:
        problems.append(f"{uid}: an evidence unit with this id already exists")

    strength = unit.get("strength")
    if strength and strength not in STRENGTHS:
        problems.append(f"{uid}: strength {strength!r} must be one of {STRENGTHS}")

    if unit.get("kind") == "project":
        if not unit.get("name") and not unit.get("parent"):
            problems.append(f"{uid}: a project unit needs `name` (or `parent`)")
    else:
        roles = {r["id"] for r in prof.get("roles", [])}
        if unit.get("role") not in roles:
            problems.append(
                f"{uid}: role {unit.get('role')!r} is not a role in master.yaml "
                f"({', '.join(sorted(roles))}) — or set `kind: project`")

    # A probe that is not a question has not been thought about.
    probe = str(unit.get("probe") or "")
    if probe and "?" not in probe:
        problems.append(f"{uid}: `probe` must be a question an interviewer asks")

    # Emphasis has to be able to match, or it fails silently forever.
    flat = " ".join(" ".join([
        str(unit.get("claim", "")), str(unit.get("name", "")),
        " ".join(str(v) for v in (unit.get("metrics") or {}).values()),
        " ".join(map(str, unit.get("keywords") or [])),
        " ".join(map(str, unit.get("stack") or [])),
    ]).split()).lower()
    for term in unit.get("emphasize") or []:
        if str(term).strip().lower() not in flat:
            problems.append(f"{uid}: emphasize {term!r} appears nowhere in the unit")
    return problems


def warnings(unit: dict) -> list[str]:
    """Worth saying, not worth blocking on.

    Numbers ought to live in `metrics` so they can be quoted verbatim later,
    but this cannot be a gate: "p99" and "GPT-4.1" read as numbers to any
    tokenizer, and a check that rejects a true claim teaches people to route
    around the tool — which is the one outcome this system cannot survive.
    """
    from .verify import _numbers
    out = []
    metric_nums = _numbers(" ".join(
        str(v) for v in (unit.get("metrics") or {}).values()))
    # "p99", "GPT-4.1", "g5.xlarge": a digit glued to a letter is part of a
    # name, not a result he is claiming.
    claim = re.sub(r"[A-Za-z]+-?\d[\w.]*", " ", str(unit.get("claim", "")))
    loose = sorted(_numbers(claim) - metric_nums)
    if loose:
        out.append(f"{unit.get('id')}: {', '.join(repr(n) for n in loose)} "
                   f"in the claim but not in `metrics` — check it is quotable")
    if not unit.get("emphasize"):
        out.append(f"{unit.get('id')}: no `emphasize` — nothing in this bullet "
                   f"will render in bold")
    return out


def _render(unit: dict) -> str:
    """One unit as YAML text, indented to sit in master.yaml's evidence list."""
    # flow style for leaf lists, matching the hand-written units above it —
    # `skills: [a, b, c]` rather than four lines per skill.
    body = yaml.dump([unit], default_flow_style=None, sort_keys=False,
                     allow_unicode=True, width=74)
    return "".join(("  " + line if line.strip() else line)
                   for line in body.splitlines(keepends=True))


def add(root: Path, units: list[dict], source_note: str = "") -> list[str]:
    """Validate and splice units into master.yaml. Returns the ids added."""
    prof = load_profile(root)
    problems: list[str] = []
    seen: set[str] = set()
    for u in units:
        problems += validate(prof, u)
        if u.get("id") in seen:
            problems.append(f"{u.get('id')}: listed twice in the same batch")
        seen.add(u.get("id"))
    if problems:
        raise JobloopError(
            "evidence rejected — master.yaml is the root of trust:\n  "
            + "\n  ".join(problems))

    path = root / "profile" / "master.yaml"
    text = path.read_text("utf-8")
    if SENTINEL not in text:
        raise JobloopError(
            f"master.yaml has no {SENTINEL!r} marker; cannot splice safely")

    blocks = []
    for u in units:
        u = dict(u)
        u.setdefault("on_master", False)
        u["added_at"] = utcnow()[:10]
        if source_note:
            u["source_note"] = " ".join(source_note.split())
        blocks.append(_render(u))

    head, _, tail = text.partition(SENTINEL)
    path.write_text(head + "\n".join(blocks) + "\n" + SENTINEL + tail, "utf-8")

    # Re-read through the real loader: a splice that produced invalid YAML, or
    # tripped verify_profile, must not survive this function.
    from .verify import verify_profile
    try:
        reloaded = load_profile(root)
    except Exception as exc:
        path.write_text(text, "utf-8")
        raise JobloopError(f"splice produced invalid YAML, rolled back: {exc}")
    bad = verify_profile(reloaded)
    if bad:
        path.write_text(text, "utf-8")
        raise JobloopError("rolled back — " + "; ".join(bad))
    return [u["id"] for u in units]


def load_draft(root: Path, source: str) -> tuple[list[dict], str]:
    data = read_yaml(Path(source) if source != "-" else draft_path(root))
    units = data.get("units") or []
    if not isinstance(units, list) or not units:
        raise JobloopError("no `units` in the draft — nothing to add")
    return units, str(data.get("raw") or "")
