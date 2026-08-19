# jobloop

Post a JD from your phone → get back a tailored resume that survives ATS
screening → the job tracks itself through your inbox → what went wrong in
interviews becomes a drilled weakness list.

```
Discord ──▶ OpenClaw (local) ──▶ jt intake ──▶ git
                                                │
                        ┌───────────────────────┘
                        ▼
        scheduled Claude (cloud or Actions, every few hours)
        tailor → verify → screen → Gmail sync → push
                        │
                        ▼
        GitHub Actions: compile PDF → ATS audit → back to Discord
```

## The guarantee

Nothing reaches a resume without **provenance** into `profile/master.yaml`.
`jt verify` mechanically rejects any bullet that invents a number, names a
technology the cited evidence doesn't support, or has no source at all.

```
$ jt verify 2026-08-18-joveo-ai-llm-engineer
FAIL — 5 provenance violation(s)
  x number '99.4%' is not supported by ['ev-phenom-toolcalling-guardrails']
  x mentions 'Kubernetes' which the cited evidence does not support
  x NO PROVENANCE — 'Built data-driven analytics on large-scale transact…'
  x cites unknown evidence id(s) ['ev-i-led-a-team-of-ten']
  x skills[Databases]: 'Snowflake' is not in the master skill inventory
```

Gaps between a JD and your history go into the screening report and the
learning ledger. They never become bullets. A resume that passes screening on
a lie just fails the interview instead.

## ATS, specifically

Keyword coverage measured against your YAML is meaningless — the ATS never
sees it. `jt ats` compiles the PDF, extracts the text back out the way a
parser does, and audits *that*:

- text actually extractable, in reading order (not multi-column soup)
- name / email / phone recoverable as text
- contact URLs present as text — anchor text of "GitHub" loses the link
- section headings a parser can map (`Experience`, `Education`, `Skills`)
- employment date ranges it can build a timeline from
- no ligature splits, no undecodable glyphs, no template leakage
- **no visually overlapping lines** — these extract fine and are invisible to
  every other check, but unreadable to a human
- keyword coverage computed on the *extracted* text, split into real gaps vs.
  word-form misses (`pipeline` vs `pipelines`), because literal matching is
  common

## Daily use

```bash
jt status                    # the pipeline, plus what's gone silent
jt show joveo                # one job in full
jt intake "<jd text or url>" # or just post it in Discord
jt worksheet <slug>          # JD asks + your best TRUE evidence, ranked
#   → Claude writes tailored.yaml
jt verify <slug> && jt build <slug> && jt ats <slug> && jt screen <slug>
```

After an interview:

```bash
jt debrief <slug>            # template → tell Claude what happened
jt debrief <slug> --apply -  # weaknesses open, drills generate
jt learn list
```

Weaknesses escalate on repeat. Closing one **requires** recorded recovery in a
later real interview — reading about a topic isn't resolution.

## Messages

Five kinds of outbound message, one mechanism. The format of each is fixed and
reproduced verbatim; exactly one paragraph varies, and it is held to the same
provenance bar as the resume — a message that oversells gets the call, and the
call is where the overselling is found out.

```bash
jt message --types                                     # who each one is for
jt message <slug> --type follow-up --scaffold --name "Neha"
#   → Claude writes the pitch
jt verify <slug> --message follow-up && jt message <slug> --type follow-up
```

| type | for |
|---|---|
| `referral` | asking someone inside the company for a referral |
| `recruiter-reply` | answering a recruiter who reached out first |
| `follow-up` | an application that has gone quiet |
| `thank-you` | within a day of an interview round |
| `outreach` | cold, to the person who would manage the role |

From Discord: `/msg job:<fragment> type:<kind> name:<contact>`, or
`/ln_msg <jd>` to go straight from a posting to the message.

`jt referral <slug>` still works and is the same code path.

## From Discord

| command | what it does |
|---|---|
| `/cv <jd>` | paste a JD → tailored CV + screening report (`/jd` is the same) |
| `/ln_msg <jd>` | paste a JD → the LinkedIn message to send about it |
| `/msg job:<frag> type:<kind>` | a message for a job already tracked |
| `/jobs [job]` | the pipeline, or one job in detail |
| `/jobstatus job:<frag> status:<s>` | move a job along |
| `/ctx <text>` | add something you built to `profile/master.yaml` |

`/ctx` is the one that compounds. Nothing reaches a CV that is not an evidence
unit, so context you never add is work the pipeline cannot use. It replies
with the claim it wrote and the `probe` — the question that claim now commits
you to answering in a room.

## Email

The Gmail connector is a Claude-side tool, so `jt` never talks to Gmail.
Claude fetches threads and pipes them in:

```bash
jt mail ingest - --auto-intake   # creates jobs from application confirmations
jt mail needs-reply
```

Classification is deterministic and deduped, so an hourly cron is safe. Status
only ever moves forward — a stray email can't demote a live process.

## State

Per-job YAML under `jobs/` is the source of truth. `jobs.db` is a derived
SQLite index, gitignored, rebuilt by `jt reindex` — because the cloud routine
and your laptop both write between pulls, and a committed SQLite binary would
corrupt. Query it freely:

```bash
jt sql "SELECT * FROM pipeline"
jt sql "SELECT * FROM open_weaknesses"
```

## Setup

```bash
uv venv && uv pip install -e .
python -m pytest tests/ -q
```

`~/.local/bin/jt` pins `JOBLOOP_ROOT` so `jt` works from any directory.
The Discord skill lives in `openclaw/jobloop/`; install with
`openclaw skills install ./openclaw/jobloop --force`.

Requires `pdflatex` and `pdftotext` locally (GitHub Actions covers both in
CI). `moderncv`/`altacv` are **not** used — `templates/resume.cls` is
self-contained.

See `CLAUDE.md` for how Claude is meant to operate this.
