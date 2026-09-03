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
   Claude cloud routine (every 3h, Gmail attached) ──────────────────┤
   GitHub Actions routine.yml (after each Discord command + 3h cron) ┤
   systemd timer on the workstation (fallback, hourly :53) ──────────┤
                                                                     ▼
                                    tailor → verify → build → ats → screen
                                    → commit → push → build.yml → Discord
```

**Judgment runs in the cloud now (2026-09-04).** Two paths, either is enough;
both use the Claude subscription, neither needs an API key:

1. **Claude cloud routine** — `jobloop routine (cloud)` at
   https://claude.ai/code/routines (id `trig_01HsVsc8q3YNSLY5pYUqmeUr`). The
   2026-08-19 finding that a cloud routine gets 403 on this private repo no
   longer holds — creating one against `adityadasika21/jobloop` returned 200.
   It has the Gmail connector attached, so `kind: mail` requests can be
   answered there. Manage it with `/schedule`.
2. **`.github/workflows/routine.yml`** — `claude-code-action` with
   `claude_code_oauth_token` (from `claude setup-token`, stored as the
   `CLAUDE_CODE_OAUTH_TOKEN` secret). Fires after every Discord command lands,
   on a 3-hourly cron, and by hand. Has the TeX toolchain, so it builds and
   audits the real PDF. No Gmail.

Both are gated by `jt work`: Claude does not start unless a Discord request is
queued or a JD is untailored. `scripts/run-routine.sh` + `scripts/routine-prompt.md`
remain the workstation fallback; `systemctl --user list-timers jobloop.timer`
shows it. Running two of the three at once is safe but wasteful — they take
the same `jobloop-write` concurrency group in Actions and rebase before
pushing, but the workstation timer does not know about the others. Disable it
(`systemctl --user disable --now jobloop.timer`) once a cloud path is
confirmed working.

`discord.yml` still does only the deterministic half (intake, scaffolds,
inbox). Keep it that way — the test `test_the_discord_workflow_does_no_thinking`
pins it — so a Discord command answers in seconds and the judgment run
follows.

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
jt cover <slug> --scaffold # → cover.yaml; fill it, then:
jt verify <slug> --cover && jt cover <slug>   # → cover.tex → cover.pdf (xelatex)
```

In an interactive session, `/apply <jd>` runs all of that plus the qualitative
fit (`docs/fit-rubric.md` + `profile/preferences.md` → `fit.md`) and interview
prep (`/prep`). `/fit`, `/cover`, `/prep`, `/scrape`, `/upskill` are the parts.

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

## Merged from ai-job-search (2026-09-04)

`adityadasika21/ai-job-search` (a fork of MadsLorentzen's Danish-market
framework, moderncv CVs) was folded into this repo and retired. What came
across, and where it lives:

| was | now |
|---|---|
| `cover_letters/cover.cls` + Lato/Raleway fonts | `templates/cover.cls`, `templates/OpenFonts/`, rendered by `jt cover` |
| 04-job-evaluation (scoring dimensions, motivation filter) | `docs/fit-rubric.md`, applied by `/fit` and `/apply` on top of `jt screen` |
| 03-writing-style | `docs/writing-style.md`; the mechanical rules are enforced by `jt cover` |
| 07-interview-prep (STAR stories, tough questions) | `docs/interview-prep.md`, used by `/prep` |
| 02-behavioral-profile + CLAUDE.md preferences | `profile/preferences.md` — wants, not claims |
| job-scraper search queries | `docs/search-queries.md`, used by `/scrape` |
| `/apply`, `/upskill` | `.claude/commands/` (rewritten around `jt`) |
| tracker CSV | `jobs/` — TCS imported as `2026-09-04-tcs-gen-ai-developer` with its old CV/letter under `legacy/` |

Dropped on purpose: moderncv CVs (he wants the Jake template `resume.cls`),
Danish portal CLIs, salary tools, `/setup` `/reset` `/expand` (onboarding for
a fork; `jt evidence` replaces `/expand`).

### Cover letters — the third claim surface

`jobs/<slug>/cover.yaml` → `jt cover` → `cover.tex` → `cover.pdf`. `opening`,
every bullet and `closing` cite evidence ids and go through the same
`verify_bullets` as resume bullets. `why_company` is about them, so
provenance cannot apply — instead it must list the `sources` (URLs actually
fetched) or it is rejected. `jt verify --cover` also rejects em-dashes and a
body over 320 words. One page, always; read the PDF before sending it.

## Resolving a job from what someone said

`resolve_slug` takes a full slug, a substring, or a whole sentence. Rare words
identify a job and common ones do not, so it scores tokens by how few jobs
contain them — "auricai" outweighs "ai engineer", which is in half the corpus.
Adjacent tokens are also glued ("auric ai" → `auricai`), because nobody knows
how a company name was slugified.

```bash
jt find "auric ai round 1 done, they asked about RAG"   # ranked candidates
```

It refuses rather than guesses when two jobs are close — two roles at one
company is the case that matters, and putting an interview on the wrong
timeline corrupts both.

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

## Outbound messages

Five types — `referral`, `recruiter-reply`, `follow-up`, `thank-you`,
`outreach`. Each has a fixed format reproduced verbatim; only the middle
paragraph (`pitch`) varies, and it is a claim surface like any bullet.

```bash
jt message --types                                   # and who each is for
jt message <slug> --type follow-up --scaffold --name "Neha"
jt verify <slug> --message follow-up
jt message <slug> --type follow-up
```

The scaffold's `_instructions` say what THAT type's paragraph is for; follow
them rather than writing a generic paragraph five times. A follow-up in
particular must give them a reason to reply, and must never count the days.

`jt referral <slug>` is `--type referral` and still works. A job recovered
from an application email has no `tailored.yaml`, and `jt verify --message`
works on it anyway — that is exactly when a follow-up gets written.

## Emphasis

`emphasize:` on an evidence unit lists the load-bearing terms it may render in
bold — the system name, the framework, the one number worth arguing about.
His own resume bolds `91.9%` and leaves `98.6%`, `10.98 RPS`, `87%` and `97%`
plain, because bolding every number bolds nothing. Deriving emphasis from
`metrics` is the obvious idea and it is wrong for that reason.

A term is only honoured where it appears verbatim in the bullet, and `jt
verify` rejects a term the cited evidence doesn't contain. Bold is a claim.

## Adding evidence (`/ctx`, `jt evidence`)

```bash
jt evidence draft "what he built, in his words"   # scaffold
#   → Claude writes the unit(s)
jt evidence add profile/pending-evidence.yaml
```

This is the most dangerous write in the system: every bullet and every message
is generated from `master.yaml`, and `jt verify` believes it absolutely. There
is **no human confirmation gate** — his explicit call, 2026-08-19. What stands
in for one:

- `probe` is required and must be a question. If he could not answer it from
  what he actually said, the claim is too strong — weaken the claim, never
  soften the probe.
- `source_note` + `added_at` record the words that produced the unit, so any
  claim can be traced back.
- `on_master: false` by default: available to tailoring at once, but his
  one-page master resume does not change until someone says so.
- The splice is textual, and rolls back if the result fails to load or fails
  `verify_profile`. Never round-trip `master.yaml` through the YAML dumper —
  it would strip every comment in it, including the rules at the top.

If the context is too vague to support an honest claim, **add nothing** and
say what you would need to know. That is a valid outcome, not a failure.

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
  is self-contained. Check `kpsewhich` before adding a package. Cover letters
  are the one **xelatex** document — `cover.cls` loads fontspec and the
  bundled fonts by relative path, so `jt cover` compiles in a scratch dir with
  `templates/cover.cls` and `templates/OpenFonts/` copied beside the .tex.
  Never `\lettercontent{...\end{itemize}}` — its trailing `\\` errors; the
  template already puts the list outside, in a Raleway wrapper.
- Negative `\vspace` in `resume.cls` is load-bearing and fragile. Overlapping
  text still extracts fine, so `jt ats`'s collision check is the only thing that
  catches it. Always run `jt ats` after touching the class.
- Jinja resolves `x.items` to `dict.items`. Context keys must not collide with
  Python attribute names.
- `jt verify` is deliberately strict. If it flags something true, fix the
  *master profile* rather than loosening the check.
- `jt` auto-commits **and pushes** with `git add -A` — `intake`, `evidence
  add`, `advance`, `debrief`, `mail ingest`. It sweeps unrelated working-tree
  changes into that commit. Commit your own work first, or pass `--no-commit`.
- `~/.gitconfig` was `CHANGE_ME@example.com`; fixed globally 2026-08-19, and
  this repo also sets its identity locally. Check `git log --format=%ae` if
  commits look mis-attributed.
- `reference/resume-source.tex` is Aditya's own authoritative `.tex`.
  `templates/resume.cls` was reverse-engineered from a compiled PDF before it
  existed. **Where they disagree, his wins** — point size, margins, list
  indents, tabular widths and heading weight are all his values now.
- `on_master: false` on an evidence unit means true and tailorable but not on
  his one-page master resume, so `jt build --master` still reproduces his page.
- To rejoin two split units under space pressure, write ONE bullet citing both
  ids; provenance is a list and `jt verify` checks the merged text against the
  union.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

Each test pins a guarantee that broke at least once. Keep them green.
