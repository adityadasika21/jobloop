# TODO

## 1. Template must match the real resume source  ← blocking, do first

Aditya supplied the authoritative `.tex` on 2026-08-18. `templates/resume.cls`
and `templates/resume.tex.j2` were reverse-engineered from a compiled PDF
before that existed, so they differ. **Where the two disagree, his source
wins.** Paste it into `reference/resume-source.tex` and reconcile:

- [ ] **`\input{glyphtounicode}` + `\pdfgentounicode=1`** — missing from
      `resume.cls` entirely. This is the thing that makes pdfLaTeX output
      reliably text-extractable; his source carries the comment "Ensure that
      generate pdf is machine readable/ATS parsable". Highest-value single
      line in this list. Add it and re-run `jt ats` to confirm the extraction
      is still clean (it passes today, but this makes it robust rather than
      lucky).
- [ ] `\documentclass[letterpaper,10pt]` — mine is 11pt.
- [ ] Margins: his `-0.5in` odd/even side, `+1in` textwidth, `-0.5in` top,
      `+1.0in` textheight. Mine drifted while fixing the two-page overflow.
- [ ] `\resumeSubHeadingListStart` uses `leftmargin=0.15in`; mine uses `0.0in`.
- [ ] `\resumeSubheading` / `\resumeProjectHeading` use `0.97\textwidth`;
      mine uses `1.0` / `1.001`.
- [ ] Section headings: his are `\large` without `\bfseries`; mine adds bold.
- [ ] **`\textbf{}` emphasis inside bullets** — his bolds the load-bearing
      terms (chatbotCXAgent, LangGraph, Graph RAG, XGrammar, 91.9%, QLoRA,
      vLLM, ModernBERT). The pipeline emits none, so generated resumes read
      flatter than his hand-written one. Needs an emphasis mechanism in
      `tailored.yaml` — probably auto-bold from the cited unit's `metrics` and
      a per-unit `emphasize:` list, so it stays provenance-bound rather than
      the model bolding whatever it likes.

### Conflict to resolve deliberately
His header links are anchor text — `Portfolio | GitHub | LinkedIn`. I changed
these to bare URLs (`github.com/adityadasika21`) because anchor text loses the
URL entirely to an ATS text extractor; `jt ats`'s `link-*` checks assert the
bare form. His version looks better to a human. **Ask him which way to go** —
this is a genuine tradeoff, not an oversight on either side.

## 2. `profile/master.yaml` is stale

- [ ] **The hiring-integrity bullet has been rewritten and is materially
      different.** Mine (from the old PDF) describes a *configuration and
      policy plane*: signal registry, feature groups, tenant overrides, resolve
      API, CEL policies. His current source describes an **LLM orchestration
      engine that investigates flagged candidate activity, correlates evidence
      across signals, and produces reviewer-facing assessments with supporting
      rationale**, backed by a policy-driven rules engine, per-tenant risk
      config, and audited review workflows. That is a much stronger, much more
      agentic claim and the evidence unit must be rewritten to match — with a
      new `probe`, new `keywords`, and `strength: core`.
- [ ] ModernBERT: his source merges it into the QLoRA bullet
      ("; separately fine-tuned a multi-task ModernBERT…"). I split it into its
      own unit. Splitting is better for tailoring granularity — keep the split
      in `master.yaml`, but the renderer should be able to re-join them when
      space is tight.
- [ ] Re-run `jt build --master` and diff against his compiled PDF until they
      match, the same way the original reconstruction was verified.

## 3. Message generation from a JD is missing

`jt referral` exists but is only half the story:

- [ ] Not exposed as a Discord command. `/jd`, `/jobs`, `/jobstatus` are live;
      there is no `/msg`. Add one that takes a job + contact name + message
      type and returns the drafted message in-channel.
- [ ] Only one message type exists (the fixed-format LinkedIn referral ask).
      Likely also wanted: recruiter reply, follow-up on a silent application,
      post-interview thank-you, and a cold outreach to a hiring manager.
      All must stay under `jt verify --referral`'s provenance rule.
- [ ] The referral format itself is fixed and must stay verbatim — only the
      middle paragraph varies. See `templates/referral.md.j2`.

## 4. Loose ends from the first routine run

- [ ] `--auto-intake` can create a duplicate job from a thread already
      processed in an earlier run. Dedup covers repeat *events* but not repeat
      *job creation*. The routine removed a duplicate Barclays stub by hand;
      the cause is still open.
- [ ] Global `~/.gitconfig` is `CHANGE_ME@example.com`, mis-attributing every
      commit in every repo. Fixed locally for jobloop only.

## 5. Still waiting on Aditya

- [ ] **Backbase** (interviewed 4 Aug) and **Auric AI** (10 Aug) have no
      recorded outcome and both need a reply. Highest-value items in the
      pipeline. `jt debrief <slug>` once he says how they went.
- [ ] His source carries three of his own TODOs: exact LinkedIn URL, confirm
      the NorthStar stack, and add a real user/download count if one exists.
