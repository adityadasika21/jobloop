"""Outbound messages: one JD in, one message out.

`jt referral` was only ever a fifth of this. A job search generates five kinds
of message and four of them had no home: replying to an inbound recruiter,
chasing an application that has gone quiet, thanking an interviewer, and cold
outreach to the person who would actually manage the role.

Every type works the same way, and it is the same way the resume works:

  * the format is FIXED and reproduced verbatim -- greeting, ask, sign-off
  * exactly ONE paragraph varies, `pitch`, written against this JD
  * that paragraph is a claim surface, so `jt verify --message <type>` holds it
    to the provenance rule. A message that oversells is worse than no message:
    it gets the call, and the call is where the overselling is discovered.

Adding a type is adding an entry to TYPES plus a template. Nothing else.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .store import JobloopError, job_dir, load_job, read_yaml, write_yaml

# The pitch guidance is what Claude is actually steered by, so it says what the
# paragraph is FOR in each case rather than restating "be relevant".
TYPES: dict[str, dict] = {
    "referral": {
        "template": "referral.md.j2",
        "summary": "LinkedIn referral ask",
        "audience": "someone already inside the company",
        "pitch": (
            "2-4 sentences of real background mapping to THIS JD — specific "
            "projects, numbers and technologies drawn from the evidence below. "
            "You are asking a near-stranger to spend their credibility, so lead "
            "with the single most relevant thing you have actually built."
        ),
    },
    "recruiter-reply": {
        "template": "messages/recruiter-reply.md.j2",
        "summary": "reply to an inbound recruiter",
        "audience": "a recruiter who contacted Aditya first",
        "pitch": (
            "2-4 sentences answering the unasked question 'is this person "
            "actually at the level of the role?'. They already want to talk, so "
            "do not sell — qualify. Name the closest real work and its scale."
        ),
    },
    "follow-up": {
        "template": "messages/follow-up.md.j2",
        "summary": "follow up on a silent application",
        "audience": "whoever the application went to, after silence",
        "pitch": (
            "2-4 sentences that give them a REASON to reply, not a reminder "
            "that they didn't. Add something the application did not already "
            "say — a shipped result, a number, work that has moved since. "
            "Never mention how long it has been."
        ),
    },
    "thank-you": {
        "template": "messages/thank-you.md.j2",
        "summary": "post-interview thank-you",
        "audience": "the interviewer, within a day of the round",
        "pitch": (
            "2-4 sentences referring to what was actually discussed and adding "
            "one thing: the better answer to the question that went badly, or "
            "the detail there wasn't time for. Check "
            "jobs/<slug>/interviews/ for what really happened. Do not claim "
            "the interview went well."
        ),
    },
    "outreach": {
        "template": "messages/outreach.md.j2",
        "summary": "cold outreach to a hiring manager",
        "audience": "the person who would manage the role, cold",
        "pitch": (
            "2-4 sentences that read as an engineer talking to an engineer "
            "about their problem, not a candidate talking about themselves. "
            "Open with the work, not the interest. Hardest audience of the "
            "five: they owe you nothing and can smell a template."
        ),
    },
}

DEFAULT_TYPE = "referral"


def resolve_type(name: str) -> str:
    """Accept a unique prefix, so `--type follow` works from Discord."""
    name = (name or DEFAULT_TYPE).strip().lower()
    if name in TYPES:
        return name
    hits = [t for t in TYPES if t.startswith(name)]
    if len(hits) == 1:
        return hits[0]
    raise JobloopError(
        f"unknown message type {name!r}; one of: {', '.join(TYPES)}"
    )


def paths(root: Path, slug: str, mtype: str) -> tuple[Path, Path]:
    """(data, rendered). Referral keeps its original location — it is already
    committed history in every tailored job, and moving it would rewrite files
    for no gain."""
    d = job_dir(root, slug)
    if mtype == "referral":
        return d / "referral.yaml", d / "referral.md"
    return d / "messages" / f"{mtype}.yaml", d / "messages" / f"{mtype}.md"


def scaffold(root: Path, slug: str, mtype: str, name: str = "") -> Path:
    from .screen import rank_evidence
    from .store import load_profile

    spec = TYPES[mtype]
    d = job_dir(root, slug)
    job = load_job(root, slug)
    prof = load_profile(root)
    jd = (d / "jd.md").read_text("utf-8") if (d / "jd.md").exists() else ""
    ranked = rank_evidence(prof, jd)[:6]

    data_path, _ = paths(root, slug, mtype)
    existing = read_yaml(data_path, default={}) if data_path.exists() else {}

    write_yaml(data_path, {
        "_instructions": (
            f"{spec['summary']} — to {spec['audience']}. "
            f"Fill `pitch`: {spec['pitch']} "
            f"List every evidence id you used in `provenance`. Do NOT change "
            f"the surrounding message format; only this paragraph varies. "
            f"Then: jt verify {slug} --message {mtype} && "
            f"jt message {slug} --type {mtype}"
        ),
        "type": mtype,
        "contact_name": name or existing.get("contact_name", ""),
        "company": job.get("company", ""),
        "role": job.get("role", ""),
        "stage": existing.get("stage", ""),
        "pitch": existing.get("pitch", ""),
        "provenance": existing.get("provenance", []),
        "_candidate_evidence": [
            {"id": u["id"], "claim": " ".join(str(u["claim"]).split()),
             "metrics": u.get("metrics") or {}, "jd_overlap": hits[:10]}
            for u, _s, hits in ranked],
    })
    return data_path


def render(root: Path, slug: str, mtype: str) -> str:
    spec = TYPES[mtype]
    data_path, _ = paths(root, slug, mtype)
    job = load_job(root, slug)
    data = read_yaml(data_path, default={})
    if not data.get("pitch"):
        raise JobloopError(
            f"{slug}: {data_path.name} has no `pitch`. Run "
            f"`jt message {slug} --type {mtype} --scaffold` and have Claude "
            f"write the paragraph."
        )

    applied = str(job.get("applied_at") or "")[:10]
    env = Environment(loader=FileSystemLoader(str(root / "templates")),
                      trim_blocks=False, lstrip_blocks=False, autoescape=False)
    out = env.get_template(spec["template"]).render(
        contact_name=data.get("contact_name") or "[Name]",
        role=data.get("role") or job.get("role", "[Role]"),
        company=data.get("company") or job.get("company", "[Company]"),
        stage=data.get("stage") or "",
        applied_on=_pretty_date(applied),
        pitch=" ".join(str(data["pitch"]).split()),
    )
    # The template's explanatory comment block leaves a newline behind it.
    return out.strip() + "\n"


def _pretty_date(iso: str) -> str:
    """'2026-08-04' -> '4 August'. Empty when unknown, so the template can
    simply omit the clause rather than print a placeholder."""
    try:
        from datetime import date
        y, m, d = (int(x) for x in iso.split("-")[:3])
        months = ["", "January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        date(y, m, d)
        return f"{d} {months[m]}"
    except (ValueError, IndexError):
        return ""
