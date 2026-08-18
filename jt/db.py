"""Rebuild the derived SQLite index from the YAML files.

Nothing here is authoritative. `reindex` drops everything and rebuilds, so a
corrupt or stale jobs.db is fixed by running it again — which is exactly why
the DB is gitignored and the YAML is not.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .store import (
    all_jobs, job_dir, load_job, load_ledger, read_text, read_yaml, JobloopError,
)


def db_path(root: Path) -> Path:
    return root / "jobs.db"


def connect(root: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path(root))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def reindex(root: Path) -> dict:
    schema = read_text(root / "schema.sql")
    dbp = db_path(root)
    if dbp.exists():
        dbp.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(dbp) + suffix)
        if p.exists():
            p.unlink()

    con = connect(root)
    con.executescript(schema)
    counts = {"jobs": 0, "events": 0, "interviews": 0,
              "artifacts": 0, "weaknesses": 0, "evidence": 0}

    for slug in all_jobs(root):
        d = job_dir(root, slug)
        job = load_job(root, slug)
        con.execute(
            """INSERT INTO jobs (slug, company, role, url, source, location,
                 work_mode, status, fit_score, keyword_coverage, stretch,
                 priority, posted_at, intake_at, applied_at, closed_at,
                 outcome, notes, dir)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (slug, job.get("company", ""), job.get("role", ""), job.get("url", ""),
             job.get("source", ""), job.get("location", ""), job.get("work_mode", ""),
             job.get("status", "queued"), job.get("fit_score"),
             job.get("keyword_coverage"), int(bool(job.get("stretch"))),
             job.get("priority", ""), job.get("posted_at", "") or None,
             job.get("intake_at", ""), job.get("applied_at", "") or None,
             job.get("closed_at", "") or None, job.get("outcome", "") or None,
             job.get("notes", ""), f"jobs/{slug}"),
        )
        counts["jobs"] += 1

        for e in job.get("events", []) or []:
            try:
                con.execute(
                    """INSERT INTO events (job_slug, ts, kind, detail, source, ref)
                       VALUES (?,?,?,?,?,?)""",
                    (slug, e.get("ts", ""), e.get("kind", "note"),
                     e.get("detail", ""), e.get("source", ""), e.get("ref")),
                )
                counts["events"] += 1
            except sqlite3.IntegrityError:
                pass  # dedupe index did its job

        for f in sorted((d / "interviews").glob("round-*.yaml")) \
                if (d / "interviews").exists() else []:
            iv = read_yaml(f, default={})
            if not iv:
                continue
            con.execute(
                """INSERT OR REPLACE INTO interviews (job_slug, round, stage,
                     format, held_at, interviewer, duration_min, questions_asked,
                     went_well, went_badly, outcome, self_rating, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, int(iv.get("round", 1)), iv.get("stage"), iv.get("format"),
                 iv.get("held_at"), iv.get("interviewer"), iv.get("duration_min"),
                 json.dumps(iv.get("questions_asked") or []),
                 json.dumps(iv.get("went_well") or []),
                 json.dumps(iv.get("went_badly") or []),
                 iv.get("outcome"), iv.get("self_rating"), iv.get("notes", "")),
            )
            counts["interviews"] += 1

        for kind, rel in (("jd", "jd.md"), ("analysis", "analysis.yaml"),
                          ("resume_tex", "resume.tex"), ("resume_pdf", "resume.pdf"),
                          ("screen_report", "screen-report.md"),
                          ("ats_report", "ats-report.md"),
                          ("referral", "referral.md")):
            p = d / rel
            if p.exists():
                con.execute(
                    """INSERT INTO artifacts (job_slug, kind, path, built_at)
                       VALUES (?,?,?,datetime(?, 'unixepoch'))""",
                    (slug, kind, f"jobs/{slug}/{rel}", int(p.stat().st_mtime)),
                )
                counts["artifacts"] += 1

    ledger = load_ledger(root)
    for w in ledger.get("weaknesses", []) or []:
        con.execute(
            """INSERT OR REPLACE INTO weaknesses (id, topic, category, severity,
                 status, occurrences, first_seen, last_seen, resolved_at,
                 resolution, drill_path, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (w["id"], w.get("topic", w["id"]), w.get("category"),
             w.get("severity", "medium"), w.get("status", "open"),
             int(w.get("occurrences", 1)), w.get("first_seen", ""),
             w.get("last_seen"), w.get("resolved_at"), w.get("resolution"),
             w.get("drill_path"), w.get("notes", "")),
        )
        counts["weaknesses"] += 1
        for ev in w.get("evidence", []) or []:
            con.execute(
                """INSERT INTO weakness_evidence (weakness_id, job_slug,
                     interview_round, ts, kind, quote, recovered)
                   VALUES (?,?,?,?,?,?,?)""",
                (w["id"], ev.get("job_slug"), ev.get("round"),
                 ev.get("ts", w.get("first_seen", "")), ev.get("kind", "interview"),
                 ev.get("quote", ""), int(bool(ev.get("recovered")))),
            )
            counts["evidence"] += 1

    con.commit()
    con.close()
    return counts


def query(root: Path, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    if not db_path(root).exists():
        reindex(root)
    con = connect(root)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()
