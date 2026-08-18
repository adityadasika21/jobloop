"""jt — the only writer of jobloop state.

Every command is deterministic. Judgment calls (what to write in a bullet,
what a bad interview answer revealed) are made by Claude and handed back here
as YAML/JSON, so the same input always produces the same state transition.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import ats as ats_mod
from . import db as db_mod
from . import intake as intake_mod
from . import learn as learn_mod
from . import mail as mail_mod
from . import render as render_mod
from . import screen as screen_mod
from . import verify as verify_mod
from .model import STATUS_ORDER, status_rank, utcnow
from .store import (
    JobloopError, all_jobs, append_event, commit_push, job_dir, load_job,
    load_profile, repo_root, resolve_slug, save_job, read_yaml, write_text,
    write_yaml,
)

# Colour only when a human is watching. _c() already checked isatty, but
# DIM/BOLD/OFF were interpolated into f-strings directly and bypassed it — so
# piping `jt status` into Discord posted raw escape codes ("[1mSTATUS").
# Blanking the constants themselves fixes every call site at once.
_TTY = sys.stdout.isatty()
OK = "\033[32m" if _TTY else ""
BAD = "\033[31m" if _TTY else ""
WARN = "\033[33m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
OFF = "\033[0m" if _TTY else ""


def _c(text: str, color: str) -> str:
    return f"{color}{text}{OFF}" if _TTY else text


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_intake(root: Path, a) -> int:
    raw = sys.stdin.read() if (a.text == "-" or not a.text) and not sys.stdin.isatty() \
        else (a.text or "")
    slug, notes = intake_mod.intake(
        root, raw, source=a.source, company=a.company, role=a.role,
        url=a.url, priority=a.priority, allow_dupe=a.allow_dupe,
    )
    print(f"{_c('intake', OK)} {slug}")
    for n in notes:
        print(f"  {_c('!', WARN)} {n}")
    if not a.no_commit:
        print(f"  {DIM}{commit_push(root, f'intake: {slug}', push=not a.no_push)}{OFF}")
    print(f"\nNext: jt worksheet {slug}")
    return 0


def cmd_worksheet(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    path = render_mod.worksheet(root, slug, top=a.top)
    job = load_job(root, slug)
    if job.get("status") == "queued":
        job["status"] = "analyzed"
        save_job(root, slug, job)
        append_event(root, slug, "analyzed", "worksheet generated", "jt")
    print(f"{_c('worksheet', OK)} {path.relative_to(root)}")
    print(f"\nClaude: read it, write jobs/{slug}/tailored.yaml, then run\n"
          f"  jt verify {slug} && jt build {slug} && jt screen {slug}")
    return 0


def cmd_verify(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    problems = verify_mod.verify_job(root, slug)
    if a.referral:
        problems += verify_mod.verify_referral(root, slug)
    if problems:
        print(_c(f"FAIL — {len(problems)} provenance violation(s)", BAD))
        for p in problems:
            print(f"  {_c('x', BAD)} {p}")
        print("\nFix tailored.yaml. Every claim must trace to profile/master.yaml.")
        return 1
    print(_c("verify OK", OK) + " — every claim traces to the master profile")
    append_event(root, slug, "verified", "provenance clean", "jt")
    return 0


def cmd_build(root: Path, a) -> int:
    if a.master:
        prof = load_profile(root)
        tailored = render_mod.master_tailored(prof)
        tex = render_mod.render_tex(root, tailored, variant="master")
        out_dir = root / "profile"
        tex_path = out_dir / "master-resume.tex"
        write_text(tex_path, tex)
        import shutil
        shutil.copy(root / "templates" / "resume.cls", out_dir / "resume.cls")
        print(f"{_c('tex', OK)} {tex_path.relative_to(root)}")
        if not a.no_pdf:
            pdf = render_mod.build_pdf(tex_path)
            print(f"{_c('pdf', OK)} {pdf.relative_to(root)}")
        return 0

    slug = resolve_slug(root, a.slug)
    tex_path = render_mod.write_job_tex(root, slug)
    print(f"{_c('tex', OK)} {tex_path.relative_to(root)}")
    if not a.no_pdf:
        try:
            pdf = render_mod.build_pdf(tex_path)
            print(f"{_c('pdf', OK)} {pdf.relative_to(root)}")
        except JobloopError as exc:
            print(f"{_c('pdf skipped', WARN)} — {exc}")
    append_event(root, slug, "tailored", "resume rendered", "jt")
    return 0


def cmd_ats(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    d = job_dir(root, slug)
    pdf = d / "resume.pdf"
    if not pdf.exists():
        raise JobloopError(f"{slug}: no resume.pdf — run `jt build {slug}` first")
    prof = load_profile(root)
    jd = (d / "jd.md").read_text("utf-8") if (d / "jd.md").exists() else ""
    tailored = read_yaml(d / "tailored.yaml", default={})
    tailored_text = " ".join(
        [b.get("text", "") for r in tailored.get("experience", []) or []
         for b in r.get("bullets", []) or []]
        + [b.get("text", "") for p in tailored.get("projects", []) or []
           for b in p.get("bullets", []) or []])

    rep = ats_mod.audit(pdf, prof, jd_text=jd, tailored_text=tailored_text)
    report = ats_mod.render_audit(rep)
    write_text(d / "ats-report.md", report)

    if a.text:
        print(rep["extracted_text"])
        return 0
    print(report)
    verdict = _c("ATS PASS", OK) if rep["passes"] else _c("ATS FAIL", BAD)
    print(f"{verdict} — report written to jobs/{slug}/ats-report.md")
    return 0 if rep["passes"] else 1


def cmd_screen(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    rep = screen_mod.screen(root, slug)
    job = load_job(root, slug)
    report = screen_mod.render_report(rep, job)
    d = job_dir(root, slug)
    write_text(d / "screen-report.md", report)
    write_yaml(d / "analysis.yaml", {
        "fit_score": rep["fit_score"],
        "keyword_coverage": rep["keyword_coverage"],
        "summary": rep["summary"], "seniority": rep["seniority"],
        "requirements": rep["requirements"],
        "scan_checks": rep["scan_checks"],
        "screened_at": utcnow(),
    })
    job["fit_score"] = rep["fit_score"]
    job["keyword_coverage"] = rep["keyword_coverage"]
    job["stretch"] = rep["seniority"]["stretch"]
    if status_rank(job.get("status", "")) < status_rank("ready") \
            and rep["passes_gate"]:
        job["status"] = "ready"
    save_job(root, slug, job)
    append_event(root, slug, "screened", f"fit {rep['fit_score']}", "jt")

    print(report)
    v = _c("GATE PASS", OK) if rep["passes_gate"] else _c("GATE FAIL", WARN)
    print(f"{v} · fit {rep['fit_score']}/100 · report at jobs/{slug}/screen-report.md")
    return 0


def cmd_status(root: Path, a) -> int:
    db_mod.reindex(root)
    rows = db_mod.query(root, "SELECT * FROM pipeline")
    if not rows:
        print("no active jobs")
        return 0
    print(f"{BOLD}{'STATUS':<11}{'FIT':>4} {'KW':>4}  {'ROUNDS':>6} "
          f"{'IDLE':>5}  COMPANY / ROLE{OFF}")
    for r in rows:
        fit = r["fit_score"] if r["fit_score"] is not None else "-"
        kw = f"{int(r['kw_pct'])}%" if r["kw_pct"] is not None else "-"
        idle = f"{r['days_since_activity']}d"
        flag = _c(" STRETCH", WARN) if r["stretch"] else ""
        print(f"{r['status']:<11}{str(fit):>4} {kw:>4}  {r['rounds']:>6} "
              f"{idle:>5}  {r['company']} — {r['role']}{flag}")
        if a.verbose:
            print(f"{DIM}            {r['slug']}{OFF}")

    closed = db_mod.query(root, """
        SELECT status, COUNT(*) n FROM jobs
        WHERE status IN ('rejected','withdrawn','offer','ghosted')
        GROUP BY status""")
    if closed:
        print("\n" + DIM + "closed: " +
              " · ".join(f"{r['n']} {r['status']}" for r in closed) + OFF)

    stale = [r for r in rows if r["days_since_activity"] is not None
             and r["days_since_activity"] >= 14
             and r["status"] in ("applied", "screening", "interview")]
    if stale:
        print(f"\n{BOLD}SILENT 14+ DAYS{OFF}  {DIM}(chase or mark ghosted){OFF}")
        for r in stale:
            print(f"  {r['days_since_activity']:>3}d  {r['company']} — {r['role']}")

    weak = db_mod.query(root, "SELECT * FROM open_weaknesses LIMIT 8")
    if weak:
        print(f"\n{BOLD}OPEN WEAKNESSES{OFF}")
        for w in weak:
            print(f"  {w['severity']:<8} x{w['occurrences']}  {w['topic']}"
                  f"{DIM}  ({w['seen_in'] or '-'}){OFF}")
    return 0


def cmd_reindex(root: Path, a) -> int:
    counts = db_mod.reindex(root)
    print(_c("reindex OK", OK) + " " +
          " · ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"{DIM}jobs.db is derived and gitignored — rebuild anytime{OFF}")
    return 0


def cmd_sql(root: Path, a) -> int:
    rows = db_mod.query(root, a.query)
    if not rows:
        print("(no rows)")
        return 0
    if a.json:
        print(json.dumps([dict(r) for r in rows], indent=2, default=str))
        return 0
    cols = rows[0].keys()
    print(" | ".join(cols))
    print("-+-".join("-" * len(c) for c in cols))
    for r in rows:
        print(" | ".join("" if r[c] is None else str(r[c]) for c in cols))
    return 0


def cmd_mail(root: Path, a) -> int:
    if a.mail_cmd == "ingest":
        msgs = mail_mod.load_messages(a.source)
        res = mail_mod.ingest(root, msgs, apply_status=not a.no_status,
                              auto_intake=a.auto_intake)
        print(f"{_c('mail', OK)} matched {res['matched']} · "
              f"created {len(res['created'])} · events +{res['events_added']} · "
              f"noise {res['noise']} · unmatched {len(res['unmatched'])}")
        for c in res["created"]:
            print(f"  {_c('+', OK)} {c['company']} — {c['role']}  ({c['slug']})")
        for c in res["status_changes"]:
            print(f"  {_c('→', OK)} {c['slug']}: {c['from']} → {c['to']}")
        for u in res["unmatched"][:10]:
            print(f"  {_c('?', WARN)} unmatched [{u['kind']}] "
                  f"{u['subject']!r} from {u['from']}")
        if res["unmatched"]:
            print(f"{DIM}  Unmatched mail may be a job you haven't tracked — "
                  f"intake it, or pass job_slug in the JSON.{OFF}")
        if not a.no_commit:
            print(f"  {DIM}{commit_push(root, 'mail sync', push=not a.no_push)}{OFF}")
        return 0

    for r in mail_mod.needs_reply(root, days=a.days):
        print(f"{r['ts'][:10]}  {r['kind']:<11} {r['company']} — {r['role']}")
        print(f"{DIM}            {r['detail']}{OFF}")
    return 0


def cmd_debrief(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    if a.apply:
        data = json.loads(sys.stdin.read()) if a.apply == "-" \
            else json.loads(Path(a.apply).read_text("utf-8"))
        path = learn_mod.save_interview(root, slug, data)
        job = load_job(root, slug)
        if status_rank(job.get("status", "")) < status_rank("interview"):
            job["status"] = "interview"
        outcome = (data.get("outcome") or "").lower()
        if outcome == "rejected":
            job["status"] = "rejected"
            job["outcome"] = "rejected"
            job["closed_at"] = utcnow()
        save_job(root, slug, job)
        append_event(root, slug, "interview",
                     f"round {data.get('round')} — {data.get('stage','')} "
                     f"→ {data.get('outcome','pending')}", "debrief")

        opened = []
        for w in data.get("weaknesses", []) or []:
            wid, is_new = learn_mod.add_weakness(
                root, w["topic"], category=w.get("category", "technical"),
                severity=w.get("severity", "medium"), job_slug=slug,
                round_=int(data.get("round", 1)), quote=w.get("quote", ""),
                notes=w.get("notes", ""))
            opened.append((wid, is_new))
            ledger_w = next(x for x in learn_mod.load_ledger(root)["weaknesses"]
                            if x["id"] == wid)
            learn_mod.drill_stub(root, ledger_w)
        for wid in data.get("recovered", []) or []:
            learn_mod.record_recovery(root, wid, slug, int(data.get("round", 1)))

        print(f"{_c('debrief', OK)} {path.relative_to(root)}")
        for wid, is_new in opened:
            tag = _c("NEW", WARN) if is_new else _c("REPEAT — severity up", BAD)
            print(f"  weakness {wid} [{tag}] → learning/drills/{wid}.md")
        for wid in data.get("recovered", []) or []:
            print(f"  {_c('recovered', OK)} {wid}")
        if not a.no_commit:
            msg = f"debrief: {slug} round {data.get('round')}"
            print(f"  {DIM}{commit_push(root, msg, push=not a.no_push)}{OFF}")
        return 0

    rnd = learn_mod.next_round(root, slug)
    job = load_job(root, slug)
    tmpl = {
        "round": rnd, "stage": "", "format": "", "held_at": utcnow()[:10],
        "interviewer": "", "duration_min": None,
        "questions_asked": [], "went_well": [], "went_badly": [],
        "outcome": "pending", "self_rating": None, "notes": "",
        "weaknesses": [{"topic": "", "category": "technical",
                        "severity": "medium", "quote": "", "notes": ""}],
        "recovered": [],
    }
    print(json.dumps(tmpl, indent=2))
    print(f"\n{DIM}# {job.get('company')} — {job.get('role')}, round {rnd}\n"
          f"# Tell Claude what happened; it fills this in and pipes it to:\n"
          f"#   jt debrief {slug} --apply -{OFF}", file=sys.stderr)
    return 0


def cmd_learn(root: Path, a) -> int:
    if a.learn_cmd == "list":
        ws = learn_mod.open_weaknesses(root)
        if not ws:
            print("no open weaknesses")
            return 0
        for w in ws:
            rec = sum(1 for e in w.get("evidence", []) if e.get("recovered"))
            print(f"{w['severity']:<8} x{w.get('occurrences',1)}  {w['id']}")
            print(f"{DIM}         {w['topic']}  · status={w.get('status')}"
                  f" · recoveries={rec}{OFF}")
        return 0

    if a.learn_cmd == "add":
        wid, is_new = learn_mod.add_weakness(
            root, a.topic, category=a.category, severity=a.severity,
            job_slug=a.job or "", quote=a.quote, kind=a.kind)
        w = next(x for x in learn_mod.load_ledger(root)["weaknesses"]
                 if x["id"] == wid)
        path = learn_mod.drill_stub(root, w)
        print(f"{_c('new' if is_new else 'repeat', OK if is_new else WARN)} "
              f"{wid} → {path.relative_to(root)}")
        return 0

    if a.learn_cmd == "recovered":
        learn_mod.record_recovery(root, a.wid, resolve_slug(root, a.job),
                                  a.round, a.quote)
        print(f"{_c('recovery recorded', OK)} for {a.wid}")
        return 0

    if a.learn_cmd == "resolve":
        learn_mod.resolve(root, a.wid, a.resolution, force=a.force)
        print(f"{_c('resolved', OK)} {a.wid}")
        return 0

    if a.learn_cmd == "practicing":
        learn_mod.set_status(root, a.wid, "practicing")
        print(f"{a.wid} → practicing")
        return 0
    return 1


def cmd_referral(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    d = job_dir(root, slug)
    path = d / "referral.yaml"
    if a.scaffold or not path.exists():
        job = load_job(root, slug)
        prof = load_profile(root)
        jd = (d / "jd.md").read_text("utf-8") if (d / "jd.md").exists() else ""
        ranked = screen_mod.rank_evidence(prof, jd)[:6]
        write_yaml(path, {
            "_instructions": (
                "Fill `pitch` with 2-4 sentences of real background mapping to "
                "this JD — specific projects, numbers, technologies drawn from "
                "the evidence below. List every evidence id you used in "
                "`provenance`. Do NOT change the surrounding message format. "
                f"Then: jt verify {slug} --referral && jt referral {slug}"),
            "contact_name": a.name or "",
            "company": job.get("company", ""),
            "role": job.get("role", ""),
            "pitch": "",
            "provenance": [],
            "_candidate_evidence": [
                {"id": u["id"], "claim": " ".join(str(u["claim"]).split()),
                 "metrics": u.get("metrics") or {}, "jd_overlap": hits[:10]}
                for u, _s, hits in ranked],
        })
        print(f"{_c('scaffold', OK)} {path.relative_to(root)}")
        print(f"Claude: write the pitch, then `jt referral {slug}`")
        return 0

    msg = render_mod.render_referral(root, slug)
    problems = verify_mod.verify_referral(root, slug)
    if problems and not a.force:
        print(_c("FAIL — pitch is not fully supported by your evidence", BAD))
        for p in problems:
            print(f"  {_c('x', BAD)} {p}")
        return 1
    write_text(d / "referral.md", msg)
    print(msg)
    append_event(root, slug, "referral", "message generated", "jt")
    return 0


def cmd_advance(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    job = load_job(root, slug)
    cur = job.get("status", "queued")
    if a.status not in STATUS_ORDER:
        raise JobloopError(f"unknown status {a.status!r}; one of {STATUS_ORDER}")
    if status_rank(a.status) < status_rank(cur) and not a.force:
        raise JobloopError(
            f"{slug} is already '{cur}'; moving back to '{a.status}' needs --force")
    job["status"] = a.status
    if a.status == "applied" and not job.get("applied_at"):
        job["applied_at"] = utcnow()
    if a.status in ("rejected", "withdrawn", "offer", "ghosted"):
        job["closed_at"] = utcnow()
        job["outcome"] = a.status
    save_job(root, slug, job)
    append_event(root, slug, a.status if a.status in
                 ("applied", "rejected", "offer", "withdrawn") else "note",
                 a.note or f"status {cur} → {a.status}", "manual")
    print(f"{slug}: {cur} → {_c(a.status, OK)}")
    if not a.no_commit:
        print(f"  {DIM}{commit_push(root, f'{slug}: {a.status}', push=not a.no_push)}{OFF}")
    return 0


def cmd_sync(root: Path, a) -> int:
    print(commit_push(root, a.message, push=not a.no_push))
    return 0


def cmd_show(root: Path, a) -> int:
    slug = resolve_slug(root, a.slug)
    job = load_job(root, slug)
    print(f"{BOLD}{job.get('company')} — {job.get('role')}{OFF}")
    print(f"{DIM}{slug}{OFF}")
    for k in ("status", "fit_score", "keyword_coverage", "work_mode",
              "priority", "url", "applied_at", "outcome"):
        if job.get(k) not in (None, "", []):
            print(f"  {k:<18} {job[k]}")
    if job.get("stretch"):
        print(f"  {_c('stretch', WARN):<18} applying over stated experience level")
    print(f"\n{BOLD}Timeline{OFF}")
    for e in job.get("events", []) or []:
        print(f"  {e.get('ts','')[:16]}  {e.get('kind','?'):<11} "
              f"{(e.get('detail') or '')[:80]}")
    d = job_dir(root, slug)
    arts = [p.name for p in sorted(d.iterdir()) if p.is_file()]
    print(f"\n{BOLD}Files{OFF}\n  " + "\n  ".join(arts))
    return 0


# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jt", description="jobloop")
    p.add_argument("--root", help="repo root (else JOBLOOP_ROOT or cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def commitflags(sp):
        sp.add_argument("--no-commit", action="store_true")
        sp.add_argument("--no-push", action="store_true")

    s = sub.add_parser("intake", help="ingest a JD (text, URL, or stdin)")
    s.add_argument("text", nargs="?", default="")
    s.add_argument("--source", default="manual")
    s.add_argument("--company", default="")
    s.add_argument("--role", default="")
    s.add_argument("--url", default="")
    s.add_argument("--priority", default="")
    s.add_argument("--allow-dupe", action="store_true")
    commitflags(s)
    s.set_defaults(fn=cmd_intake)

    s = sub.add_parser("worksheet", help="emit the tailoring worksheet")
    s.add_argument("slug")
    s.add_argument("--top", type=int, default=14)
    s.set_defaults(fn=cmd_worksheet)

    s = sub.add_parser("verify", help="enforce provenance on tailored.yaml")
    s.add_argument("slug")
    s.add_argument("--referral", action="store_true")
    s.set_defaults(fn=cmd_verify)

    s = sub.add_parser("build", help="render resume.tex (+pdf)")
    s.add_argument("slug", nargs="?", default="")
    s.add_argument("--master", action="store_true",
                   help="build the untailored master resume")
    s.add_argument("--no-pdf", action="store_true")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("ats", help="audit the built PDF the way an ATS parses it")
    s.add_argument("slug")
    s.add_argument("--text", action="store_true",
                   help="dump the extracted text instead of the report")
    s.set_defaults(fn=cmd_ats)

    s = sub.add_parser("screen", help="score against the JD and write the report")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_screen)

    s = sub.add_parser("status", help="the pipeline")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("show", help="one job in detail")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("reindex", help="rebuild jobs.db from the YAML")
    s.set_defaults(fn=cmd_reindex)

    s = sub.add_parser("sql", help="query the derived index")
    s.add_argument("query")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_sql)

    s = sub.add_parser("mail", help="fold Gmail into job timelines")
    msub = s.add_subparsers(dest="mail_cmd", required=True)
    m = msub.add_parser("ingest")
    m.add_argument("source", nargs="?", default="-",
                   help="JSON file of messages, or - for stdin")
    m.add_argument("--no-status", action="store_true")
    m.add_argument("--auto-intake", action="store_true",
                   help="create job records for untracked application emails")
    commitflags(m)
    m = msub.add_parser("needs-reply")
    m.add_argument("--days", type=int, default=3)
    s.set_defaults(fn=cmd_mail)

    s = sub.add_parser("debrief", help="record an interview")
    s.add_argument("slug")
    s.add_argument("--apply", nargs="?", const="-", default=None,
                   help="apply a filled debrief JSON (- for stdin)")
    commitflags(s)
    s.set_defaults(fn=cmd_debrief)

    s = sub.add_parser("learn", help="the weakness ledger")
    lsub = s.add_subparsers(dest="learn_cmd", required=True)
    lsub.add_parser("list")
    m = lsub.add_parser("add")
    m.add_argument("topic")
    m.add_argument("--category", default="technical")
    m.add_argument("--severity", default="medium")
    m.add_argument("--job", default="")
    m.add_argument("--quote", default="")
    m.add_argument("--kind", default="self_report")
    m = lsub.add_parser("recovered")
    m.add_argument("wid")
    m.add_argument("job")
    m.add_argument("round", type=int)
    m.add_argument("--quote", default="")
    m = lsub.add_parser("resolve")
    m.add_argument("wid")
    m.add_argument("resolution")
    m.add_argument("--force", action="store_true")
    m = lsub.add_parser("practicing")
    m.add_argument("wid")
    s.set_defaults(fn=cmd_learn)

    s = sub.add_parser("referral", help="LinkedIn referral ask (fixed format)")
    s.add_argument("slug")
    s.add_argument("--scaffold", action="store_true")
    s.add_argument("--name", default="", help="contact's first name")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_referral)

    s = sub.add_parser("advance", help="move a job's status")
    s.add_argument("slug")
    s.add_argument("status")
    s.add_argument("--note", default="")
    s.add_argument("--force", action="store_true")
    commitflags(s)
    s.set_defaults(fn=cmd_advance)

    s = sub.add_parser("sync", help="commit and push")
    s.add_argument("-m", "--message", default="jobloop sync")
    s.add_argument("--no-push", action="store_true")
    s.set_defaults(fn=cmd_sync)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = Path(args.root).resolve() if args.root else repo_root()
        return args.fn(root, args)
    except JobloopError as exc:
        print(f"{_c('error', BAD)}: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
