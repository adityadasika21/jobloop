# ATS parse audit

**PASS** — 0 critical, 0 high · 4342 chars extracted

Keyword coverage **on extracted text**: 70% exact · 76% allowing word-form variants

| | Check | Result |
|---|---|---|
| ✅ | `text-extractable` | 4342 chars recovered by the text extractor |
| ✅ | `name` | name found in extracted text |
| ✅ | `email` | email found |
| ✅ | `phone` | phone digits recovered |
| ✅ | `link-portfolio` | portfolio URL present as text (projectindex.online) |
| ✅ | `link-github` | github URL present as text (github.com/adityadasika21) |
| ✅ | `link-linkedin` | linkedin URL present as text (linkedin.com/in/adityadasika21) |
| ✅ | `section-experience` | 'experience' section recognised as 'experience' |
| ✅ | `section-education` | 'education' section recognised as 'education' |
| ✅ | `section-skills` | 'skills' section recognised as 'technical skills' |
| ✅ | `date-ranges` | 3 parseable date range(s) for 2 role(s) (+education) |
| ✅ | `reading-order` | 39/42 long lines agree between reading-order and layout extraction |
| ✅ | `glyphs` | no undecodable glyphs |
| ✅ | `no-template-leakage` | no template artifacts |
| ✅ | `ligatures` | 0 possible ligature splits |
| ✅ | `content-fidelity` | 100.0% of intended terms survived extraction |
| ✅ | `ats-keyword-coverage` | 70% of JD requirement terms present in the EXTRACTED text |
| ✅ | `no-overlap` | no overlapping text |
| ✅ | `page-count` | 1 page(s) |

## Present, but in the wrong word form

The concept is on the resume under a different inflection. Literal ATS matching misses these, so adopt the JD's exact wording where the claim stays true.

`deploying`, `domain`, `gate`, `harnesses`

## JD terms genuinely absent

Add only what is true; the rest are gaps for the ledger.

`dspy`, `frameworks`, `gcp`, `infrastructure`, `kubernetes`, `learning`, `llm-powered`, `machine`, `pinecone`, `recruitment`, `reduce`, `software`, `tech`, `tgi`, `workflows`
