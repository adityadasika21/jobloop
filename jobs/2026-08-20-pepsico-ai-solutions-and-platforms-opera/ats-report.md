# ATS parse audit

**FAIL** — 0 critical, 1 high · 4199 chars extracted

Keyword coverage **on extracted text**: 36% exact · 42% allowing word-form variants

| | Check | Result |
|---|---|---|
| ✅ | `text-extractable` | 4199 chars recovered by the text extractor |
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
| ✅ | `reading-order` | 37/40 long lines agree between reading-order and layout extraction |
| ✅ | `glyphs` | no undecodable glyphs |
| ✅ | `no-template-leakage` | no template artifacts |
| ✅ | `ligatures` | 0 possible ligature splits |
| ❌ | `ats-keyword-coverage` _(HIGH)_ | 36% of JD requirement terms present in the EXTRACTED text |
| ✅ | `no-overlap` | no overlapping text |
| ✅ | `page-count` | 1 page(s) |

## Fixes

- **ats-keyword-coverage** — This is the number the ATS scores, not the one in tailored.yaml.

## Present, but in the wrong word form

The concept is on the resume under a different inflection. Literal ATS matching misses these, so adopt the JD's exact wording where the claim stays true.

`audit`, `calls`, `environment`, `failure`, `incident`, `instrument`, `pipelines`, `prompts`, `services`, `technologies`, `version`

## JD terms genuinely absent

Add only what is true; the rest are gaps for the ledger.

`aks`, `alerting`, `analysis`, `app`, `applications`, `autogen`, `automate`, `azure`, `capabilities`, `center`, `chargeback`, `chunking`, `components`, `consoles`, `conventions`, `cost-effective`, `crew.ai`, `cross-domain`, `cross-functional`, `data`, `debuggability`, `discipline`, `distributed`, `domains`, `eks`, `equivalent`, `execution`, `existing`, `explaining`, `exposure`, `field`, `finops`, `flexibility`, `flows`, `fundamentals`, `gcp`, `gpu`, `handling`, `health`, `histories`
