# Drill — Quantifying AI delivery impact for executives: cycle time, story-to-code conversion, review acceleration

**Severity:** medium · **Occurrences:** 1 ·
**Status:** open · **First seen:** 2026-08-20

## Where this cost you

- 2026-08-20 · 2026-08-20-globallogic-forward-deployed-engineer-irc299 round -: (no quote)

## The answer you should be able to give cold

I have not run an executive value-measurement programme, so I answer this with
what I have actually measured and how I would extend it.

What I have done is put numbers on AI systems where there previously weren't
any. On the chatbot agent I built an LLM evaluation framework — pass@k and an
LLM-as-judge rubric — that gates every release across all twelve nodes, and I
instrumented it with LiteLLM and Langfuse so per-node cost, latency and the
full trace are auditable. That turned "the agent feels worse this week" into a
number someone can act on. On the serving side I held the fine-tuned Qwen
deployment to a golden baseline — 1.0s median, 1.4s P95, zero failures across
5,510 requests — and took that service's test coverage from 7% to 78%. On the
analytics service I took coverage from 63% to over 90%. Those are the same
shape of metric an engineering executive cares about: a baseline, a gate, and
a trend.

What I have not done is tie that to delivery economics — cycle time,
story-to-code conversion, review turnaround — or present it to a C-level
audience. The instrumentation instinct transfers; the stakeholder framing is
the part I would be learning on the job, and I would rather say that than
claim a track record I don't have.

## Follow-ups you must survive

1. Your eval framework gates releases — what did it actually stop, and did you
   ever have to override the gate to ship? What did that cost?
2. How did you validate the LLM judge itself? A judge that agrees with you is
   not the same as a judge that is right.
3. Baseline of 1.0s median across 5,510 requests — what was the traffic mix,
   and would that baseline have caught a regression that only shows up on long
   contexts?
4. If I gave you a 200-engineer org and one quarter, what is the first metric
   you would instrument for AI-assisted delivery, and how would you avoid the
   obvious gaming of it?
5. A VP says your acceleration numbers are noise from a small sample. What is
   your response, and what would you have had to set up beforehand to answer
   that?

## What to actually build or read

- Instrument **this repo**. `jobloop` is a real AI-assisted delivery loop with
  a git history: measure intake→tailored→verified wall-clock per job, how many
  `jt verify` runs it takes to get clean, and the ATS/fit delta between first
  and final build. That is a genuine story-to-code cycle-time dataset on work
  he actually did, and it can become an evidence unit.
- Write the one-page executive readout from that data — baseline, intervention,
  delta, confidence, and what it does not prove. Practise it out loud in 3
  minutes. The artifact is the drill.
- Read DORA's four keys and Google's DevEx/SPACE framing, specifically for how
  they handle the gaming problem — that is the follow-up most likely to sink
  the answer.

## Done when

- [ ] Answered cold, out loud, without notes
- [ ] Survived the follow-ups above
- [ ] Came up in a real interview and went well
      → `jt learn recovered quantifying-ai-delivery-impact-for-executives-cy <job> <round>`
