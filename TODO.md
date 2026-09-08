# TODO

## 2026-09-08 — routines removed

- [x] ~~Cloud routine~~ — all scheduled routines deleted: systemd timers and
      units, `run-routine.sh`, `routine-prompt.md`, `.github/workflows/routine.yml`.
      The Claude cloud routine `trig_01HsVsc8q3YNSLY5pYUqmeUr` is disabled
      (the API cannot delete it). Cause is written up in CLAUDE.md.
- [ ] `jobs/2026-09-07-flipkart-engineers` is a **half-finished draft** — the
      routine wrote `tailored.yaml` and hit the session limit before trimming.
      It verifies clean but builds to 2 pages; needs a cut to one. Also its
      role parsed as "engineers" (the JD never states a title; it is SDE-2).
      Flipkart SDE-2 is not an AI-central role — check `preferences.md` before
      spending time on it.
- [ ] Raw context goes in `profile/notes-inbox.md`; turn it into evidence units
      with `jt evidence draft` / `jt evidence add` before it can reach a resume.

## 2026-09-04 — merge + cloud

- [ ] **Cloud is parked.** The Claude cloud routine
      (`trig_01HsVsc8q3YNSLY5pYUqmeUr`) was tested (clone, TeX install, jt
      all fine; Discord egress blocked) and then DISABLED on 2026-09-04 at
      Aditya's request so it does not spend subscription tokens on its own.
      Re-enable from https://claude.ai/code/routines when wanted. `routine.yml` waits
      on the `CLAUDE_CODE_OAUTH_TOKEN` secret (`claude setup-token` →
      `gh secret set CLAUDE_CODE_OAUTH_TOKEN`). Once either works, disable the
      workstation timer: `systemctl --user disable --now jobloop.timer`.
- [ ] `~/Work/repos/ai-job-search` is retired; its final state is committed
      locally (not pushed). Delete the directory when you are sure.
- [ ] Darwinbox FDE (`2026-09-04-darwinbox-forward-deployed-engineer`): resume
      built and verified, fit 80/100 by the rubric; cover letter and prep not
      yet written — `/cover` and `/prep`.
- [ ] TCS interview (2026-08-29) outcome unknown — `/j tcs ...` when you hear.

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

## 2b. Token burn — closed 2026-08-19

- [x] ~~An idle repo cost ~20M cache-read tokens a day~~ — the routine started
      Claude every hour whether or not anything had happened, and 68% of a run
      was 26 turns each re-reading the same 21.7k preamble. Both timers now
      call one gated worker: `jt work` answers "is there anything to do"
      deterministically and for free, and Claude does not start unless the
      answer is yes. Work means a queued Discord request or an untailored JD.
      **An idle day now costs nothing.**
- [x] ~~Gmail swept 19 companies hourly~~ — it is a `kind: mail` request now
      (`/j check my mail`). It was the only reason a quiet repo ever woke up.
- [ ] **Consequence, and it is real:** nothing watches your inbox any more. A
      rejection or an interview invite will not appear in `jt status` until
      you ask for a sync. If that bites, the fix is one queued `mail` request
      a day — ~1/24th of what it used to cost — say the word.

## 2c. Settled 2026-08-20

- [x] **ModernBERT**, not mmBERT — his notes use mmBERT loosely; the shipped
      model is ModernBERT and the resume is right. Noted in the unit so it does
      not get "corrected" later.
- [x] **Blueleaves started May 2022**, not September — the profile was already
      right, so years-of-experience stands at ~4.3.
- [x] **NorthStar** is a better story than the profile told: the HQ visit led
      to a continuing relationship — Royal Enfield approached him about a role
      and about other motorcycle-accessory collaborations. The app itself is
      archived and he was asked to stop distributing it; that is in the unit's
      probe, not the claim, so he is prepared for the question without putting
      the negative on the page.

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
