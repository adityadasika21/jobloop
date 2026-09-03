# Search queries — `/scrape`

Used by `.claude/commands/scrape.md`. Anything found goes through `jt intake`; jobs/ is the
only tracker (dedupe against `jt status` and `jt find`).

## Search Sites

Primary (India job market):
- **linkedin.com/jobs** — largest signal for tech roles in India, filter by Hyderabad / Bangalore / Remote
- **naukri.com** — largest Indian job board; strong for mid-senior tech roles
- **instahyre.com** — curated tech roles; good signal-to-noise for AI/ML
- **wellfound.com** (AngelList) — startup roles, remote-friendly, strong AI/ML presence
- **cutshort.io** — India-focused tech hiring, good for AI/ML

Secondary (direct searches):
- Google `site:careers.<company>.com "LLM"` or `"AI engineer"` for target companies
- LinkedIn company pages → Jobs tab

## Query Categories

### Priority 1: AI/LLM Engineer (core target)

These match the strongest and most desired career direction.

```
site:linkedin.com/jobs "LLM Engineer" Hyderabad
site:linkedin.com/jobs "AI Engineer" "LangGraph" India
site:linkedin.com/jobs "LLM Engineer" Bangalore
site:naukri.com "LLM Engineer" Hyderabad OR Bangalore
site:naukri.com "AI Engineer" "LangGraph" OR "vLLM" OR "fine-tuning"
site:instahyre.com "LLM" "agentic" India
"LLM Engineer" site:wellfound.com remote
"AI Engineer" "RAG" "fine-tuning" site:cutshort.io
```

### Priority 2: ML Engineer / Agentic AI

Strong technical overlap; includes teams building AI products with production ML.

```
site:linkedin.com/jobs "ML Engineer" "LLM" Hyderabad OR Bangalore
site:linkedin.com/jobs "Machine Learning Engineer" "fine-tuning" India
site:naukri.com "ML Engineer" "PyTorch" "production" Hyderabad OR Bangalore
site:linkedin.com/jobs "Agentic AI" engineer India
site:naukri.com "GenAI Engineer" Hyderabad OR Bangalore OR Remote
"MLOps Engineer" "LLM" site:wellfound.com India
```

### Priority 3: AI Research Engineer / Applied AI

Research-leaning but production-oriented; labs, AI-first companies.

```
site:linkedin.com/jobs "AI Research Engineer" India
site:linkedin.com/jobs "Applied AI Engineer" Hyderabad OR Bangalore OR Remote
site:linkedin.com/jobs "Research Engineer" "LLM" India
"Applied Scientist" "NLP" OR "LLM" site:naukri.com India
site:wellfound.com "AI Research" engineer India
```

### Priority 4: Backend / AI Platform Engineer (wider net)

Platform, infra, and backend roles with meaningful AI/LLM components.

```
site:linkedin.com/jobs "AI Platform Engineer" India
site:linkedin.com/jobs "Backend Engineer" "LLM" OR "GenAI" Hyderabad OR Bangalore
site:naukri.com "Platform Engineer" "AI" OR "LLM" Hyderabad OR Bangalore
site:linkedin.com/jobs "Software Engineer" "LangChain" OR "LangGraph" India
```

### Suggested roles you may not have considered

Based on your profile — strong production LLM engineering + eval/observability + fine-tuning:
- **"LLM Evaluation Engineer"** — dedicated eval roles at AI companies (OpenAI, Cohere, Weights & Biases, Arize AI); directly matches your pass@k / LLM-judge eval framework work
- **"Inference Engineer"** — vLLM serving, quantization, cost optimization roles at AI infra companies
- **"Conversational AI Engineer"** — dialogue management, intent recognition, NLU; matches your ModernBERT + chatbotCXAgent work
- **"AI Solutions Engineer"** — customer-facing technical roles at AI tooling companies (LangChain, LlamaIndex, Weights & Biases); your production LangGraph experience is rare

```
site:linkedin.com/jobs "LLM Evaluation" engineer India OR Remote
site:linkedin.com/jobs "Inference Engineer" "vLLM" OR "quantization" India OR Remote
site:linkedin.com/jobs "Conversational AI Engineer" India
"AI Solutions Engineer" site:wellfound.com
```

## Location Filter

When evaluating results, apply this priority order:
- **Ideal:** Hyderabad (on-site or hybrid), Remote (India or global)
- **Acceptable:** Bangalore (on-site or hybrid)
- **Borderline:** Other Indian metros (Mumbai, Pune, Chennai) — flag for user decision
- **Too far:** Roles requiring relocation outside India (flag; user said open to discussing)

## Date Filter

Only include jobs posted within the last 14 days, or with an application deadline that has not yet passed. If a posting date cannot be determined, include it but flag as "date unknown".

## Deal-breaker Filter

Skip postings that are clearly:
- Pure frontend roles (React/Vue/Angular with no AI/ML component)
- Junior or entry-level postings (titles like "Junior Engineer", "Associate", "Fresher")
- Non-tech roles (sales, marketing, operations)

## Adapting Queries

If the user specifies a focus area, select queries from the matching category and generate 2-3 custom queries. For example:
- "/scrape agentic" → Priority 1 + Priority 4 queries + custom agentic-specific queries
- "/scrape fine-tuning" → Priority 1 + Priority 2 + queries targeting QLoRA / PEFT / Unsloth keywords
- "/scrape remote" → all priority categories with `Remote` or `Work from home` filter
