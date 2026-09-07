# Fit — Applied AI Engineer II @ Deloitte (US Deloitte Technology Product Engineering, Hyderabad)

Qualitative pass over `jt screen` (mechanical fit 58/100, keyword coverage 27%), applying
`docs/fit-rubric.md` with `profile/preferences.md`. Requisition 360900.

| Dimension | Score | Notes |
|---|---|---|
| Technical skills | 80/100 | Python, React, Node.js, SQL/NoSQL, PyTorch, LangChain, LangGraph, unit testing all direct. The whole GenAI list is his day job: LLM integration, RAG pipelines, prompt engineering, vector search, evaluations, agent orchestration. Cloud-native via AWS, serverless Cloud Functions, microservices, Docker/Helm. Cost-aware engineering is a real strength (halved inference cost, per-node cost tracing). |
| Experience match | 78/100 | JD asks 1–3 years; he has ~4.3 total and ~1.4 explicitly AI-titled, and the JD says experience is the most relevant factor. "Engineer II" matches his current level exactly. He has both halves the role wants: shipped full-stack products (Blueleaves, the fraud admin console) and shipped agentic AI. |
| Behavioural fit | 58/100 | The friction. `preferences.md` puts consulting and IT-services firms at lower priority and flags process-heavy environments; Deloitte is one of the largest. Mitigating: this is the internal Product Engineering org, which describes itself as a product shop with daily deployments, and the JD's language (action over planning, lean experimentation, own the cost) matches how he actually works. |
| Location | PASS | Hyderabad, his home city. Travel 10% is well inside what he accepted for Darwinbox (25–40%). |
| Career alignment | 65/100 | AI is central to the role and he would own GenAI features end to end, including cost. But the products are Deloitte's internal tooling rather than an AI-first product, and the JD's stack list leans enterprise (C#/.NET, Java, Angular, Azure) in a way his does not. |

**Overall: 72/100 — Good Fit.** Apply.

## Real gaps (do not paper over)

- **Half the language list.** Angular, C#, .NET, Java and TensorFlow are absent. The JD says
  "most of the following" and he has 7 of 12, so this is survivable, but a C#/.NET-heavy team
  is a genuine mismatch (`known_gaps: csharp-dotnet`).
- **Hyperscaler AI services.** AWS yes, but never Azure OpenAI, Bedrock or Vertex AI
  (`known_gaps: gcp-vertex-ai`). The concepts transfer; the consoles were never used.
- **MLflow and Azure DevOps** are named and unused. LangFuse is the one from that list he has,
  and it is on the resume.
- **Infrastructure-as-code.** Docker and Helm charts, yes. No Terraform or equivalent
  application-level IaC on record.
- **Formal design-artefact vocabulary** (BCD, sequence/state/ERD diagrams) is not in his
  evidence. He does the work; the notation is not something he can claim.
- **Degree** is B.Tech Mechanical, not CS. The JD lists CS/SWE/DS/ML "or related discipline"
  and says experience matters most, so this is a flag rather than a blocker.

## What to lead with

The JD's own emphasis is cost accountability ("owning the inference, token, and cloud cost of
what you build"). That is his single most differentiating claim: QLoRA on vLLM at roughly half
the cost of hosted GPT-4.1, with per-node cost and latency in Langfuse. The resume leads the
Phenom block with agentic architecture and puts the cost bullet fourth; in a cover letter or
screen, open with cost.
