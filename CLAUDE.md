# jobloop

Aditya's job application, tracking, and learning loop. Post a JD from Discord →
a tailored, ATS-verified resume comes back → the job is tracked through Gmail to
its outcome → interview debriefs become a drilled weakness list.

## The one rule

**No claim without provenance.** Every generated bullet, headline, and referral
pitch must cite evidence unit IDs from `profile/master.yaml`, and may not state
a number or name a technology those units don't support. `jt verify` enforces
this and exits non-zero. Do not work around it — if a claim can't be verified,
it is either false or the master profile is missing something true.

When a JD asks for something Aditya hasn't done, it goes in the screening
report as a gap and into the learning ledger. It never becomes a bullet.
A resume that passes screening on a lie fails the interview instead, which is
worse — the whole point is being *un-rejectable when probed*.

## Architecture

```
Discord ──▶ discordBot (Cloud Run) ──▶ repository_dispatch ──▶ GitHub Actions
                                                                     │
   systemd timer (this machine, hourly :53) ──▶ claude -p ───────────┤
                                                                     ▼
                                    tailor → verify → build → ats → screen
                                    Gmail sync → commit → push → Discord
```

The routine runs **locally**, not in the cloud: a cloud routine cannot reach a
private repo without the Claude GitHub App connection, which is gated behind
Team/Enterprise settings this account can't configure. Proven — a probe routine
against the public `NorthStar` repo creates fine (200), the identical call
against private `jobloop` returns 403. Local also means `pdflatex` is available,
so the real PDF and ATS audit happen; the cloud path couldn't do that.

`scripts/run-routine.sh` + `scripts/routine-prompt.md` are the routine.
`systemctl --user list-timers jobloop.timer` shows when it next fires.

## State model

`jobs/<slug>/*.yaml`, `learning/ledger.yaml`, and `profile/master.yaml` are the
**source of truth**. `jobs.db` is a derived SQLite index, gitignored, rebuilt by
`jt reindex`. Never hand-edit `jobs.db`; never commit it.

`jt` is the only writer of state. Use a `jt` command rather than editing YAML by
hand — the commands maintain the event timeline, dedupe, and status ordering.

## Workflow for a new JD

```bash
jt intake "<jd text or url>" --source discord   # usually already done
jt worksheet <slug>        # JD requirements + best-matching TRUE evidence, ranked
# → you write jobs/<slug>/tailored.yaml from the worksheet
jt verify <slug>           # MUST pass
jt build <slug>            # tailored.yaml → resume.tex → resume.pdf
jt ats <slug>              # audits the compiled PDF as a parser sees it
jt screen <slug>           # fit score, requirement matrix, 6-second scan
```

### Writing `tailored.yaml`

Work from the top of the worksheet's ranked evidence. Then:

- **Reorder** so the first bullets answer the JD's first required items.
- **Rephrase in the JD's exact vocabulary** where the claim stays true. Highest-
  leverage move for ATS keyword matching, which is often literal: if the JD says
  "pipelines" and the evidence says "pipeline", use the plural. `jt ats` reports
  which misses are word-form and which are real gaps.
- **Drop** what the JD doesn't care about. Cutting is tailoring.
- **Never upgrade** scope, seniority, ownership, or team size.
- One page (≤14 experience bullets).

Look for non-obvious matches before declaring a gap. The hiring-integrity
platform is HR-tech domain experience; the local-LLM project is on-device
inference experience. `jt worksheet` surfaces role domains for this reason.

## Interview debriefs

```bash
jt debrief <slug>                  # prints a JSON template
jt debrief <slug> --apply -        # pipe the filled JSON back
```

Extract weaknesses from what actually went wrong, with the interviewer's words
in `quote`. Repeats escalate severity automatically. A weakness closes only with
recorded recovery in a later real interview — reading about a topic is not
resolution.

Then write `learning/drills/<id>.md`: the 60–90 second spoken answer grounded in
real evidence, five follow-ups, and the smallest useful thing to build. Prefer
shipping something small — it can become a real evidence unit later.

## Gmail sync

Gmail is an MCP tool only Claude can call, so `jt` never talks to Gmail. Fetch
threads, then hand them over:

```bash
jt mail ingest -   # stdin: [{thread_id, from, subject, date, snippet|body}]
jt mail needs-reply
```

**Read-only. Never send, reply, label, trash, or mark spam.** The routine's
allowlist enforces this, but honour it in interactive use too.

`jt` classifies and dedupes deterministically and only moves a job forward — a
stray email cannot demote a live process. Search the companies in `jt status`,
not the whole inbox.

## Referral messages

Fixed format, reproduced verbatim — only the middle paragraph varies.

```bash
jt referral <slug> --scaffold --name "Priya"
jt verify <slug> --referral
jt referral <slug>
```

## Editing `profile/master.yaml`

Add an evidence unit when Aditya has genuinely done something new. Keep units
atomic, quote metrics verbatim, fill in `probe` with what an interviewer will
ask — if he can't answer the probe, the unit is written too strongly.

`keywords` is JD-facing vocabulary for what was *actually* done. Not a place to
park aspirations, and never edited to chase a specific JD. Things he hasn't done
go in `known_gaps`.

## Things that will bite you

- `jobs.db` is derived. Rebuild with `jt reindex`, don't fix it in place.
- LaTeX: `moderncv` and `altacv` are **not installed**. `templates/resume.cls`
  is self-contained. Check `kpsewhich` before adding a package.
- Negative `\vspace` in `resume.cls` is load-bearing and fragile. Overlapping
  text still extracts fine, so `jt ats`'s collision check is the only thing that
  catches it. Always run `jt ats` after touching the class.
- Jinja resolves `x.items` to `dict.items`. Context keys must not collide with
  Python attribute names.
- `jt verify` is deliberately strict. If it flags something true, fix the
  *master profile* rather than loosening the check.
- `jt` auto-commits with `git add -A`, so it sweeps unrelated working-tree
  changes into a commit labelled "mail sync". Commit your own work first.
- `~/.gitconfig` had `CHANGE_ME@example.com`; this repo now sets its own
  identity locally. Check `git log --format=%ae` if commits look mis-attributed.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

Each test pins a guarantee that broke at least once. Keep them green.
