# Drill — OpenTelemetry and agent telemetry pipelines: semantic conventions, span correlation across prompts/tool calls/retrieval

**Severity:** medium · **Occurrences:** 1 ·
**Status:** open · **First seen:** 2026-08-20

## Where this cost you

- 2026-08-20 · 2026-08-20-pepsico-ai-solutions-and-platforms-opera round -: Familiarity with OpenTelemetry, distributed tracing, and telemetry pipelines

## The answer you should be able to give cold

Lead with the substance, name the toolchain honestly, do not pretend it was OTel.

> "I've done the tracing problem, on a different stack. chatbotCXAgent is a
> LangGraph system with 12 orchestrated nodes, and once you have that many hops
> a failure is useless without the trace — you can't tell a bad retrieval from
> a bad plan from a malformed tool call by looking at the final answer. So I
> instrumented it with LiteLLM and Langfuse: every node emits cost and latency,
> and a run is reconstructable end to end as a single trace. That's what gated
> releases — the eval framework, pass@k and an LLM-as-judge rubric, runs across
> all 12 nodes, and I need per-node attribution to know *which* node regressed
> rather than just that the score dropped. The concepts carry over directly:
> a Langfuse trace/span/generation is a span tree, node name and model
> provider are attributes, and correlating a prompt to its tool call to its
> retrieval is parent-child spans. What I haven't done is OpenTelemetry
> specifically — the OTel SDK, a collector, exporters, or the GenAI semantic
> conventions. I'd be learning the standard and the pipeline, not the idea."

The trap is padding this into a claim. "Langfuse is basically OTel" is wrong and
an observability interviewer will take it apart — Langfuse is an LLM-specific
backend, not a vendor-neutral wire format with a collector in front of it.

## Follow-ups you must survive

1. What's in a span for one agent node — attributes, events, status? What would
   you set on a tool call that failed schema validation?
2. Langfuse gave you per-node cost. How would you compute cost *per run* across
   a graph that fans out, and where does that aggregation belong — the SDK, the
   collector, or the query?
3. Why do semantic conventions matter if you're the only team emitting? What
   breaks the day a second team names the same field `model` vs `gen_ai.model`?
4. Sampling: you can't trace 100% of production forever. What's your rule for
   which agent runs get sampled, and how do you avoid throwing away the failures?
5. Your trace shows a 40-second run and a wrong answer. Walk me from that trace
   to a root cause across the 12 nodes — what do you look at, in what order?

## What to actually build or read

Ship the smallest real thing, so this can become an evidence unit instead of a
reading note:

- Instrument IndexNotes' Graph RAG pipeline with the OTel Python SDK — one span
  per stage (PDF parse → local-LLM extraction → JSON validation → Neo4j write),
  parent-child linked, with the model name and token counts as attributes.
- Run an OTel Collector locally and export to any backend (Jaeger is enough).
  The point is touching the collector/exporter split, not the UI.
- Emit one deliberately failing run and confirm the failing stage's span carries
  the error status and is findable without reading logs.
- Then read the OTel GenAI semantic conventions and rename your attributes to
  match. Noticing what you'd already named differently is the whole lesson.

## Done when

- [ ] Answered cold, out loud, without notes
- [ ] Survived the follow-ups above
- [ ] Came up in a real interview and went well
      → `jt learn recovered opentelemetry-and-agent-telemetry-pipelines-sema <job> <round>`
