-- =============================================================================
-- jobloop derived index.
--
-- This database is DISPOSABLE. The source of truth is the YAML under jobs/,
-- learning/, and profile/. `jt reindex` drops and rebuilds this file from them.
-- Never write to it directly and never commit it (see .gitignore) — a committed
-- SQLite binary corrupts the moment the cloud routine and the local machine
-- both write between pulls.
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS pipeline;
DROP VIEW  IF EXISTS open_weaknesses;
DROP TABLE IF EXISTS weakness_evidence;
DROP TABLE IF EXISTS weaknesses;
DROP TABLE IF EXISTS interviews;
DROP TABLE IF EXISTS artifacts;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS jobs;

-- ---------------------------------------------------------------------------
CREATE TABLE jobs (
    slug            TEXT PRIMARY KEY,          -- 2026-08-18-joveo-llm-engineer
    company         TEXT NOT NULL,
    role            TEXT NOT NULL,
    url             TEXT,
    source          TEXT,                      -- discord | manual | backfill | email
    location        TEXT,
    work_mode       TEXT,                      -- remote | hybrid | onsite
    status          TEXT NOT NULL,             -- see status_order() in jt/model.py
    fit_score       INTEGER,                   -- 0-100, from jt screen
    keyword_coverage REAL,                     -- 0-1, from jt screen
    stretch         INTEGER DEFAULT 0,         -- 1 = knowingly applying over-level
    priority        TEXT,                      -- high | medium | low
    posted_at       TEXT,
    intake_at       TEXT NOT NULL,
    applied_at      TEXT,
    closed_at       TEXT,
    outcome         TEXT,                      -- offer | rejected | withdrawn | ghosted
    notes           TEXT,
    dir             TEXT NOT NULL              -- path relative to repo root
);

CREATE INDEX idx_jobs_status   ON jobs(status);
CREATE INDEX idx_jobs_company  ON jobs(company);
CREATE INDEX idx_jobs_intake   ON jobs(intake_at DESC);

-- Append-only timeline. Every state change leaves a row here.
CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    job_slug    TEXT NOT NULL REFERENCES jobs(slug) ON DELETE CASCADE,
    ts          TEXT NOT NULL,
    kind        TEXT NOT NULL,   -- intake|tailored|applied|email|screen|interview
                                 -- |assessment|offer|rejected|withdrawn|note
    detail      TEXT,
    source      TEXT,            -- gmail:<thread_id> | discord | manual | routine
    ref         TEXT             -- external id, e.g. gmail thread/message id
);

CREATE INDEX idx_events_job ON events(job_slug, ts);
CREATE UNIQUE INDEX idx_events_dedupe ON events(job_slug, kind, ts, COALESCE(ref,''));

CREATE TABLE artifacts (
    id          INTEGER PRIMARY KEY,
    job_slug    TEXT NOT NULL REFERENCES jobs(slug) ON DELETE CASCADE,
    kind        TEXT NOT NULL,   -- resume_tex | resume_pdf | screen_report
                                 -- | analysis | referral | jd
    path        TEXT NOT NULL,
    built_at    TEXT,
    commit_sha  TEXT
);

CREATE INDEX idx_artifacts_job ON artifacts(job_slug);

-- ---------------------------------------------------------------------------
CREATE TABLE interviews (
    id              INTEGER PRIMARY KEY,
    job_slug        TEXT NOT NULL REFERENCES jobs(slug) ON DELETE CASCADE,
    round           INTEGER NOT NULL,
    stage           TEXT,        -- recruiter_screen | technical | system_design
                                 -- | coding | hiring_manager | onsite | final
    format          TEXT,        -- phone | video | onsite | take_home | async
    held_at         TEXT,
    interviewer     TEXT,
    duration_min    INTEGER,
    questions_asked TEXT,        -- JSON array
    went_well       TEXT,        -- JSON array
    went_badly      TEXT,        -- JSON array
    outcome         TEXT,        -- advanced | rejected | pending | no_response
    self_rating     INTEGER,     -- 1-5
    notes           TEXT,
    UNIQUE(job_slug, round)
);

CREATE INDEX idx_interviews_job ON interviews(job_slug, round);

-- ---------------------------------------------------------------------------
-- The learning loop. Weaknesses are opened by interview debriefs and by
-- screening gaps, and closed only by later evidence of recovery.
CREATE TABLE weaknesses (
    id            TEXT PRIMARY KEY,      -- kebab topic slug, e.g. system-design-scaling
    topic         TEXT NOT NULL,
    category      TEXT,                  -- technical | behavioural | communication
                                         -- | domain | process
    severity      TEXT NOT NULL,         -- critical | high | medium | low
    status        TEXT NOT NULL,         -- open | practicing | resolved | accepted
    occurrences   INTEGER NOT NULL DEFAULT 1,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT,
    resolved_at   TEXT,
    resolution    TEXT,                  -- how it was demonstrably closed
    drill_path    TEXT,
    notes         TEXT
);

CREATE INDEX idx_weak_status ON weaknesses(status, severity);

-- Which interview (or screening gap) produced the signal. This is what makes
-- severity escalation defensible rather than a feeling.
CREATE TABLE weakness_evidence (
    id            INTEGER PRIMARY KEY,
    weakness_id   TEXT NOT NULL REFERENCES weaknesses(id) ON DELETE CASCADE,
    job_slug      TEXT REFERENCES jobs(slug) ON DELETE SET NULL,
    interview_round INTEGER,
    ts            TEXT NOT NULL,
    kind          TEXT NOT NULL,        -- interview | screen_gap | self_report
    quote         TEXT,                 -- what was actually asked / what went wrong
    recovered     INTEGER DEFAULT 0     -- 1 = came up again and went well
);

CREATE INDEX idx_wev_weak ON weakness_evidence(weakness_id, ts);

-- ---------------------------------------------------------------------------
CREATE VIEW pipeline AS
SELECT
    j.slug, j.company, j.role, j.status, j.fit_score,
    ROUND(j.keyword_coverage * 100) AS kw_pct,
    j.stretch,
    (SELECT COUNT(*) FROM interviews i WHERE i.job_slug = j.slug) AS rounds,
    (SELECT MAX(ts) FROM events e WHERE e.job_slug = j.slug)      AS last_activity,
    CAST(julianday('now') - julianday(COALESCE(
        (SELECT MAX(ts) FROM events e WHERE e.job_slug = j.slug), j.intake_at
    )) AS INTEGER) AS days_since_activity
FROM jobs j
WHERE j.status NOT IN ('rejected', 'withdrawn', 'closed')
ORDER BY days_since_activity DESC;

CREATE VIEW open_weaknesses AS
SELECT
    w.id, w.topic, w.category, w.severity, w.status, w.occurrences,
    w.first_seen, w.last_seen,
    (SELECT COUNT(*) FROM weakness_evidence we
      WHERE we.weakness_id = w.id AND we.recovered = 1) AS recoveries,
    GROUP_CONCAT(DISTINCT we.job_slug) AS seen_in
FROM weaknesses w
LEFT JOIN weakness_evidence we ON we.weakness_id = w.id
WHERE w.status IN ('open', 'practicing')
GROUP BY w.id
ORDER BY
    CASE w.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2 ELSE 3 END,
    w.occurrences DESC;
