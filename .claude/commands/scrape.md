# /scrape — find new postings

Optional `$ARGUMENTS`: a focus ("agentic", "remote", "fine-tuning") or "broad".

1. Read `docs/search-queries.md` and `profile/preferences.md`. Run the Priority 1 queries
   (all categories if "broad"; the focus category first if one was given) with WebSearch,
   in parallel. Last 14 days only.
2. Pre-filter on title/snippet; WebFetch only promising results. Apply the deal-breaker and
   location filters from `preferences.md`.
3. Dedupe against `jt status -v` and `jt find "<company> <role>"` — jobs/ is the only tracker.
4. Present a table (fit High/Medium/Low, title, company, location, deadline, URL) with 2–3
   bullets per High match. Never invent a posting.
5. For each one the user picks: `jt intake "<full text>" --url <url> --source scrape`, then
   `/apply <slug>` on request.
