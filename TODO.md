# TODO

Everything that was actionable in the previous list is done (2026-08-19).
What remains needs Aditya, or needs a deploy.

## 1. Waiting on Aditya

- [x] ~~**Backbase**~~ — rejected. Recorded 2026-08-19. The drafted follow-up
      was deleted rather than sent, and the one durable signal from the round
      (they pressed on guardrails, high bar on AI) is open as a self-reported
      weakness with a drill:
      `learning/drills/production-llm-guardrails-end-to-end.md`.
- [x] ~~**Auric AI**~~ — round 1 recorded 2026-08-19 from what he said in
      Discord: done, waiting for feedback, questions on RAG, entity resolution
      and grouping entities, answered fine overall. `outcome: pending`. No
      weakness opened — "fine" is not a weakness. Tell me when feedback lands.
- [ ] The date of that round is unknown; he didn't say and I didn't guess. The
      tracked Auric AI thread is dated 7 Aug if that is the one.
- [ ] **Debrief on the day.** Two rounds have now lost their detail before
      anyone wrote them down, and Backbase's is unrecoverable — no questions,
      no quotes, just an impression. The ledger escalates on repeats and can
      only do that if the first occurrence is specific.
- [ ] Three of his own TODOs are still in `reference/resume-source.tex`:
      the exact LinkedIn URL, confirming the NorthStar stack, and a real
      user/download count for NorthStar if one exists. The first two are
      one-line fixes to `profile/master.yaml`; the third would be a genuinely
      strong number if it exists, and stays absent until it does.

## 2. Needs a deploy, not a decision

- [ ] `/msg`, `/cv`, `/ln_msg` and `/ctx` are written and their Actions
      handlers are live, but Discord does not know they exist until they are
      registered: `DISCORD_TOKEN=... node discord/registerCommands.js` in the
      discordBot repo, then redeploy the Cloud Run function so the new files
      in `discord/commands/` ship.
- [x] ~~`ANTHROPIC_API_KEY`~~ — not happening, by design. Judgment runs on the
      workstation against the Claude Code subscription. Actions now queues to
      `inbox/` and the routine drains it; `claude-code-action` is gone from
      `discord.yml` and a test keeps it gone.
- [x] ~~`tailor.yml`~~ — deleted 2026-08-19. It gated on a key that will never
      exist; the routine's section 2 does the same work with pdflatex present.
- [x] ~~`jobloop-inbox.timer`~~ — installed 2026-08-19, every 3 minutes. An
      idle tick is a `git pull` and an exit; Claude only starts when something
      is actually queued.

## 2b. Token burn — the hourly routine, not the JDs

- [ ] **The hourly routine starts a full Claude session every hour whether or
      not anything happened.** The last several runs did the same thing:
      tailorable → nothing, then a Gmail sweep across all 19 tracked
      companies, then a summary. `created 0 · events +0` three runs running.
      The Gmail sweep is the recurring cost, not the tailoring.
      Options, in rough order of saving: drop to every 3-4 hours; sweep only
      companies with a live process instead of all 19; or gate the run so
      Claude only starts when there is tailorable work, a queued request, or
      it is the Nth hour for a mail check. Say which and I will do it.
- [ ] `DISCORD_WEBHOOK` is what attaches the built PDF to the Discord reply —
      the bot's `/postmessage` route only forwards text, so without the
      webhook `/cv` returns the screening report but not the resume itself.

## 3. Small and deliberate

- [ ] Education dates render as "August 2018 – May 2022"; his source writes
      "Aug. 2018 – May 2022" there while using full month names everywhere
      else. Left alone rather than encoding an inconsistency — say the word if
      you want the abbreviation back.

---

## Done 2026-08-19

**Template reconciled with the real source.** `reference/resume-source.tex` is
now in the repo, and `templates/resume.cls` carries his values, not the
reverse-engineered ones: `\input{glyphtounicode}` + `\pdfgentounicode=1`
(missing entirely, and the reason extraction worked by luck rather than by
design), 10pt, his margins, `leftmargin=0.15in`, `0.97\textwidth`, and section
headings without the added bold. `jt build --master` now extracts to text
identical to his compiled source except for the two differences that are
deliberate — the ModernBERT split and the education date format.

**Bold means something again.** `emphasize:` on an evidence unit lists the
load-bearing terms a bullet may render in `\textbf{}`; `jt verify` rejects a
term the cited evidence doesn't contain, so emphasis is provenance-bound like
every other claim. Deriving it from `metrics` was the obvious idea and it is
wrong: his page bolds 91.9% and leaves 98.6%, 10.98 RPS, 87% and 97% plain.

**Header links: anchor text**, his call, made with the tradeoff on the table —
`Portfolio | GitHub | LinkedIn` reads better to a human and loses the URL to a
text extractor. `identity.link_style` records the choice, `jt ats` now reports
which form it actually recovered instead of asserting one, and the test pins
the choice rather than one of the options.

**`master.yaml` caught up.** The hiring-integrity bullet was rewritten from his
current source: it now describes the **LLM orchestration engine that
investigates flagged candidate activity and produces reviewer-facing
assessments**, not a configuration and policy plane. The config-plane work is
still true, so it survives as its own unit marked `on_master: false` —
available to a platform JD, absent from the one-page master.

**Message generation exists.** `jt message` with five types — referral,
recruiter-reply, follow-up, thank-you, outreach — each a fixed format with one
varying paragraph held to the provenance rule. `/msg` in Discord dispatches to
a new Actions handler that scaffolds, writes the pitch, verifies it, and posts
the result. `jt referral` is unchanged and is the same code path.

**The duplicate-job cause is closed.** Dedup covered repeat *events* but not
repeat job *creation*: a later message on an already-filed thread guessed the
role differently, `match_job` scored it below threshold, and auto-intake made a
second stub. A thread is now identity — once it belongs to a job it keeps
belonging to it. Regression test included, and it fails without the fix.

**`~/.gitconfig`** is `Aditya Dasika <akhil.dasika47@gmail.com>` globally.
