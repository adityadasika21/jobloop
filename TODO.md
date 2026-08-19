# TODO

Everything that was actionable in the previous list is done (2026-08-19).
What remains needs Aditya, or needs a deploy.

## 1. Waiting on Aditya

- [ ] **Backbase** (interviewed 4 Aug) and **Auric AI** (10 Aug) have no
      recorded outcome. Highest-value items in the pipeline. Say how they went
      and `jt debrief <slug> --apply -` records them; weaknesses open and
      drills generate from what actually went wrong.
      A follow-up for Backbase is already drafted, verified and waiting at
      `jobs/2026-08-18-backbase-ai-engineer/messages/follow-up.md` — read it
      before it goes anywhere.
- [ ] Three of his own TODOs are still in `reference/resume-source.tex`:
      the exact LinkedIn URL, confirming the NorthStar stack, and a real
      user/download count for NorthStar if one exists. The first two are
      one-line fixes to `profile/master.yaml`; the third would be a genuinely
      strong number if it exists, and stays absent until it does.

## 2. Needs a deploy, not a decision

- [ ] `/msg` is written and the Actions handler for it is live, but Discord
      does not know the command exists until it is registered:
      `DISCORD_TOKEN=... node discord/registerCommands.js` in the discordBot
      repo, then redeploy the Cloud Run function so `commands/msg.js` ships.
- [ ] `jobloop` repo secret `ANTHROPIC_API_KEY` is what lets `/msg` write the
      pitch rather than returning a scaffold to fill in by hand.

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
