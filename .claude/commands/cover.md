# /cover — cover letter for a tracked job

`$ARGUMENTS`: a job slug or anything `jt find` can resolve, optionally followed by the
addressee's name.

1. `jt cover <slug> --scaffold [--name <Name>]` → `jobs/<slug>/cover.yaml` with the JD's
   top-ranked evidence attached.
2. Fill it per `docs/writing-style.md` and the scaffold's `_instructions`. Only cite evidence
   ids from `profile/master.yaml`; only state company facts from URLs you fetched (put them in
   `why_company.sources`). No em-dashes. Under 320 body words.
3. `jt verify <slug> --cover && jt cover <slug>`; fix until clean.
4. Read `jobs/<slug>/cover.pdf`: one page, signature block with the body, bullets in the same
   font as the body. Send it with SendUserFile.
