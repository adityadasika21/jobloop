# Drill — Distributed-system resiliency: retries, backoff, and production failure modes

**Severity:** medium · **Occurrences:** 1 ·
**Status:** open · **First seen:** 2026-08-19

## Where this cost you

- 2026-08-19 · 2026-08-19-cure-fit-sde2-backend-engineer round -: Ability to reason about scalability, latency, retries, resiliency, and production failure scenarios.

## The answer you should be able to give cold

The honest frame: say what you have actually operated, then say where your
experience stops. Do not narrate textbook resiliency patterns as if you had run
them.

> "The closest I've come to reasoning about failure at load is serving Qwen
> models on vLLM on an AWS g5.xlarge — I load-tested it to 10.98 RPS at 98.6%
> success, so the number I care about is what the other 1.4% was and whether it
> was the model, the queue, or the box. On the agent side I built the
> observability that makes failure visible before it's an incident: LiteLLM and
> Langfuse tracing gives per-node cost, latency and a full trace across all 12
> nodes, and an evaluation gate — pass@k and an LLM-as-judge rubric — runs on
> every release, so a node that regresses doesn't ship. For failure *prevention*
> rather than detection, the tool-calling layer is the real example: instead of
> retrying on a bad parse, I made the bad output unrepresentable with XGrammar
> constrained decoding and schema-validated JSON, which took tool-routing to
> 91.9% and eliminated malformed tool calls in live traffic. The design idea I'd
> carry over is that one: prefer making the failure impossible to catching it
> downstream. What I have *not* owned is a retry/backoff/circuit-breaker
> topology across a fleet of services under consumer traffic — my production
> ownership at Blueleaves was Node.js and Firebase Cloud Functions, which is
> serverless, so the platform absorbed most of that for me."

The last sentence is the one that keeps this un-rejectable when probed. Say it.

## Follow-ups you must survive

1. "What *was* the 1.4% at 10.98 RPS?" — if you can't say whether it was
   timeouts, OOM, or malformed output, the whole load-testing claim gets
   discounted. Know the failure mode by name.
2. "You retried nothing? What happens when a tool call fails for a reason
   constrained decoding can't fix — the database is down, not the JSON?" —
   this is the real gap; answer what you'd do, and flag it as a design you
   haven't shipped.
3. "Your eval gate blocks a release when one node of twelve regresses. What
   does that do to your deploy cadence, and who overrides it?" — a gate nobody
   can override gets deleted; a gate everyone overrides is theatre.
4. "Firebase absorbed retries for you — so what did you actually see fail in
   production at Blueleaves?" — you cut manual operational errors by ~90% across
   POS/CRM/inventory/procurement; talk about integration failures between those
   internal systems, which is real and yours.
5. "Idempotency: your resolve API is consumed by both the reviewer console and
   the live detection pipeline. If a caller retries a config write, what
   happens?" — versioned definitions are your answer to consumer stability;
   be precise about whether that also makes writes safe to repeat.

## What to actually build or read

Smallest useful thing, and it can become a real evidence unit:

- **Ship it:** put a retry policy with exponential backoff + jitter and a
  circuit breaker in front of one real outbound dependency in IndexNotes (the
  Ollama extraction call is a good target — it genuinely times out). Log every
  retry with attempt number and outcome so you can quote a number afterwards.
- **Then break it on purpose:** kill Ollama mid-ingest and record what the
  pipeline does — how many papers were lost, how many were reprocessed twice.
  The duplicate-processing answer is the idempotency story you don't have yet.
- **Read, but only after building:** the AWS "timeouts, retries and backoff
  with jitter" article and the Stripe idempotency-key design. Both are short and
  both are about the exact question in follow-up 5.
- **Do not** claim distributed-systems resiliency on a resume until the above
  exists and has a number attached to it.

## Done when

- [ ] Answered cold, out loud, without notes
- [ ] Survived the follow-ups above
- [ ] Came up in a real interview and went well
      → `jt learn recovered distributed-system-resiliency-retries-backoff-an <job> <round>`
