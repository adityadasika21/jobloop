# /upskill — what to learn next, from real gaps

Optional `$ARGUMENTS`: a slug or URL for targeted mode; none for aggregate mode.

Sources of truth for gaps (never the JD wish-list alone):
- `jobs/*/screen-report.md` → "Real gaps" and "JD terms absent" sections
- `profile/master.yaml` → `known_gaps`
- `jt learn list` → open weaknesses from real interviews (highest weight: these cost a round)

1. Aggregate mode: collect gaps across all non-closed jobs (`jt sql "SELECT slug, fit_score FROM jobs"`),
   weight by `(100 - fit_score)/100` and by how many JDs share the gap; interview weaknesses
   count triple. Targeted mode: gaps for that one job.
2. Diff against master.yaml skills and skill_groups (be generous with synonyms).
3. Write `learning/upskill-YYYY-MM-DD.md`: gap heatmap (gap, count, weight, kind:
   tooling/domain/soft/credential), then a plan — for each of the top 5, the smallest thing
   to *build* that would become a real evidence unit, plus 1–2 web-searched resources.
   Building beats reading: a shipped artefact is what `jt evidence add` can record.
4. Offer `jt learn add "<topic>" --kind self_report` for gaps worth drilling now.
