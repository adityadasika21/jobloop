# /apply — JD in, application out

`$ARGUMENTS` is a job posting: a URL, pasted text, or an existing job slug. Produce the full
application through `jt` — never by hand-writing LaTeX. Every step below is mandatory unless
the fit verdict says stop.

Read `CLAUDE.md` first if it is not already in context. The one rule: **no claim without
provenance into `profile/master.yaml`**. If the JD asks for something Aditya has done but
master.yaml does not record, run `jt evidence draft "<his words>"`, write the unit, `jt
evidence add` — never put it straight into a bullet.

1. **Intake.** If `$ARGUMENTS` is a URL, WebFetch it and pass the full text. Then
   `jt intake "<text>" --url <url>` (or resolve an existing slug with `jt find`). Note the slug.
2. **Screen + fit.** `jt worksheet <slug>` then `jt screen <slug>` for the mechanical score.
   Then apply `docs/fit-rubric.md` with `profile/preferences.md` and write
   `jobs/<slug>/fit.md` (table, verdict, gaps, travel/location/seniority flags). Present the
   verdict. Skip only if the user said so or the fit is Poor and there is no stated reason to
   stretch; otherwise continue.
3. **Resume.** Write `jobs/<slug>/tailored.yaml` from the worksheet (JD's exact vocabulary,
   reorder so the first bullets answer the first required items, one page, ≤14 bullets).
   `jt verify <slug> && jt build <slug> && jt ats <slug> && jt screen <slug>`. Read the PDF
   with the Read tool: one page, headline on one line, no orphaned heading. Iterate.
4. **Cover letter.** `jt cover <slug> --scaffold`, fill `cover.yaml` following
   `docs/writing-style.md` (opening = the most relevant shipped thing; `why_company` only from
   URLs you fetched, listed in `sources`; 3–5 bullets; closing on how he works).
   `jt verify <slug> --cover && jt cover <slug>`. Read `cover.pdf`: exactly one page, signature
   with the body, bullet font matches body.
5. **Interview prep.** Run `/prep <slug>`.
6. **Deliver.** Send `resume.pdf` and `cover.pdf` with SendUserFile. Report: fit verdict, real
   gaps (from `screen-report.md` and `fit.md`), anything left unverified. `jt sync -m
   "apply: <slug>"` if the user's workflow expects the repo pushed.

Company facts in the letter must come from pages you actually fetched. If a claim cannot be
verified, say it in general terms or leave it out.
