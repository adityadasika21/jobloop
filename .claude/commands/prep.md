# /prep — interview preparation for a tracked job

`$ARGUMENTS`: a job slug (or text `jt find` can resolve). Output: `jobs/<slug>/prep.md`.

1. Read `jobs/<slug>/jd.md`, `screen-report.md`, `fit.md` (if present), `tailored.yaml`, and
   `docs/interview-prep.md`. Read `profile/master.yaml` for the cited units' `probe:` lines.
2. Write `prep.md` with:
   - **Opening story** ("tell me about yourself"): 60–90 seconds, anchored on the bullet that
     best answers the JD's first required item.
   - **Bullet → probe table**: every bullet in `tailored.yaml`, the unit's `probe`, and a
     two-sentence answer. If he could not answer a probe, say so — that bullet is written too
     strongly and should be softened in master.yaml, not defended.
   - **STAR stories** from `docs/interview-prep.md` mapped to this JD's responsibilities.
   - **Gap answers**: one honest answer per real gap in `screen-report.md` / `fit.md`
     (e.g. "have you implemented an MCP server?" → consumed daily, not built; here is what I
     would build first).
   - **Questions to ask them**, role-specific, from `docs/interview-prep.md`.
   - **Company facts** only from URLs you fetched, cited inline.
3. `jt learn list` — if an open weakness is relevant, link its drill.
4. After the interview: `jt debrief <slug>`.
