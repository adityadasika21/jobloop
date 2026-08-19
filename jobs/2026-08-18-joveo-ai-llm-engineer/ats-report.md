# ATS parse audit

**PASS** — 0 critical, 0 high · 4294 chars extracted

Keyword coverage **on extracted text**: 70% exact · 76% allowing word-form variants

| | Check | Result |
|---|---|---|
| ✅ | `text-extractable` | 4294 chars recovered by the text extractor |
| ✅ | `name` | name found in extracted text |
| ✅ | `email` | email found |
| ✅ | `phone` | phone digits recovered |
| ✅ | `link-portfolio` | portfolio present as anchor text ('portfolio') — the URL projectindex.online is NOT recoverable by a text extractor |
| ✅ | `link-github` | github present as anchor text ('github') — the URL github.com/adityadasika21 is NOT recoverable by a text extractor |
| ✅ | `link-linkedin` | linkedin present as anchor text ('linkedin') — the URL linkedin.com/in/adityadasika21 is NOT recoverable by a text extractor |
| ✅ | `section-experience` | 'experience' section recognised as 'experience' |
| ✅ | `section-education` | 'education' section recognised as 'education' |
| ✅ | `section-skills` | 'skills' section recognised as 'technical skills' |
| ✅ | `date-ranges` | 3 parseable date range(s) for 2 role(s) (+education) |
| ✅ | `reading-order` | 39/42 long lines agree between reading-order and layout extraction |
| ✅ | `glyphs` | no undecodable glyphs |
| ✅ | `no-template-leakage` | no template artifacts |
| ✅ | `ligatures` | 0 possible ligature splits |
| ✅ | `ats-keyword-coverage` | 70% of JD requirement terms present in the EXTRACTED text |
| ✅ | `no-overlap` | no overlapping text |
| ✅ | `page-count` | 1 page(s) |

## Present, but in the wrong word form

The concept is on the resume under a different inflection. Literal ATS matching misses these, so adopt the JD's exact wording where the claim stays true.

`deploying`, `domain`, `gate`, `harnesses`

## JD terms genuinely absent

Add only what is true; the rest are gaps for the ledger.

`dspy`, `frameworks`, `gcp`, `infrastructure`, `kubernetes`, `learning`, `llm-powered`, `machine`, `pinecone`, `recruitment`, `reduce`, `software`, `tech`, `tgi`, `workflows`
