# Interview prep

STAR stories and stock answers grounded in `profile/master.yaml`. Every unit there has a
`probe:` — the question that bullet earns — so `/prep <slug>` pairs each resume bullet with
its probe. After the interview: `jt debrief <slug>` (what went wrong becomes a drill).

## STAR Format

Structure answers as: **Situation** (context), **Task** (your responsibility), **Action** (what you did), **Result** (outcome).

Keep answers to 1-2 minutes. Be specific. End with what you learned or would do differently.

## Ready-Made STAR Examples

### 1. chatbotCXAgent — Production Agentic Platform (System Design & Ownership)
**S:** Phenom People needed a production chatbot platform that could handle enterprise-grade workflows — intent recognition, dialogue state, tool routing, and knowledge retrieval — all orchestrated reliably at scale.
**T:** Architect and ship the full agentic system from scratch on LangGraph, making it production-ready for real users.
**A:** Designed a 12-node LangGraph orchestration handling intent recognition, dialogue state management, tool-routing, and Graph RAG retrieval. Enforced tool-calling reliability with XGrammar constrained decoding and schema-validated JSON outputs. Built a custom eval framework (pass@k, LLM-judge rubric) gating every pipeline change before release.
**R:** Raised tool-routing accuracy to 91.9%, eliminated malformed tool calls in production, and shipped to real enterprise users.
**Use for:** "Tell me about a complex system you designed", "How do you ensure reliability in AI systems?", "Describe a project you owned end-to-end"

### 2. QLoRA Fine-Tuning & vLLM Serving — Inference Cost Optimization (Cost & Performance)
**S:** Phenom's chatbot was running on hosted GPT-4.1, which was expensive and introduced latency and dependency on a third-party API.
**T:** Replace hosted LLM with a fine-tuned, self-hosted model that matches or exceeds performance at lower cost.
**A:** Fine-tuned Qwen models via QLoRA (Unsloth, NF4 quantization) on vLLM / AWS EC2 g5.xlarge (A10G). Ran load testing to validate production-readiness. Instrumented LiteLLM + Langfuse for per-node cost and latency observability.
**R:** Achieved 10.98 RPS at 98.6% success rate under load, roughly halving inference cost versus hosted GPT-4.1.
**Use for:** "Tell me about a time you optimized a system for cost or performance", "Experience with model serving", "How do you evaluate self-hosted vs. hosted LLMs?"

### 3. ModernBERT Multi-Task Fine-Tuning — NLU Accuracy Improvement (ML Engineering)
**S:** The NLU layer of the chatbot (intent classification + NER) was running at 87% accuracy, which was causing downstream routing errors in the pipeline.
**T:** Improve NLU accuracy meaningfully without adding latency or architectural complexity.
**A:** Fine-tuned a multi-task ModernBERT model in PyTorch using differential learning rates, label smoothing, and uncertainty-weighted multi-task loss to jointly train intent classification and NER.
**R:** Improved NLU accuracy from 87% to 97%, a 10-point gain that directly reduced routing errors in the downstream pipeline.
**Use for:** "Tell me about a time you improved an ML model's performance", "Experience with multi-task learning or BERT fine-tuning", "How do you approach debugging poor model accuracy?"

### 4. IndexNotes — Knowledge Graph Pipeline (Independent Project / Initiative)
**S:** Scientific papers are siloed — there's no good way to query across papers for conceptual relationships between methods, datasets, and findings.
**T:** Build a personal project that ingests PDFs, extracts entities and relationships using local LLMs, and makes them queryable via a graph.
**A:** Built an automated pipeline: PDF → PyMuPDF extraction → local LLM (Ollama, quantized) for entity/relationship extraction → structured JSON → Neo4j. Designed the schema to support Graph RAG queries enabling multi-hop traversal.
**R:** Created a knowledge graph with 40+ concepts and 17+ typed relationships across 3 research papers (PINNs, Hamiltonian GNNs, topological materials). Fully local, cost-zero inference.
**Use for:** "Tell me about a personal project", "Experience with knowledge graphs or Graph RAG", "What do you build outside of work?"

### 5. Blueleaves Farms — End-to-End Production Systems (Ownership at Scale)
**S:** Blueleaves Farms was running 5+ locations on manual and fragmented systems, leading to procurement errors, inventory mismatches, and operational inefficiency.
**T:** Build and own the full production software stack — POS, CRM, inventory, procurement, e-commerce — as the sole full-stack engineer.
**A:** Designed scalable backend workflows on Firebase Cloud Functions and Node.js (invoicing, inventory sync, order lifecycle, RBAC). Built forecasting and analytics models for demand estimation and inventory planning. Integrated multiple internal systems end-to-end.
**R:** Serving 10,000+ monthly transactions across 5+ locations; cut manual operational errors by roughly 90%.
**Use for:** "Tell me about a time you owned a project end-to-end", "Experience with data-driven decision-making", "Tell me about a time you worked without much oversight"

## Common Tough Questions

### "Why did you leave [previous company]?" / "Why are you open to new opportunities?"
> I've built and shipped the core agentic infrastructure at Phenom — the orchestration layer, the eval framework, the fine-tuned models. I'm looking for a role where I can apply this production LLM experience to a harder or broader problem, ideally at a company where AI is more central to the product rather than one component of a larger HR platform.

### "You don't have a CS degree."
> I pivoted from Mechanical Engineering by building things — starting with forecasting models at Blueleaves, then scaling up to production agentic systems with fine-tuned models at Phenom. The lack of a formal CS degree means I've had to be deliberate about what I learned, and that shows up in the results: 91.9% tool-routing accuracy, halved inference cost, 10-point NLU improvement. I'd rather be evaluated on what I've shipped than what's on my transcript.

### "Where do you see yourself in 5 years?"
> Leading a small, high-impact AI/ML team or owning an AI platform at a company where LLMs are central to the product. I want to go deeper on the research-to-production pipeline — not just running fine-tuning jobs, but understanding the models well enough to make the right architectural decisions at each stage.

### "What's your biggest weakness?"
> I move fast and tend to iterate toward a working system rather than documenting comprehensively first. I've gotten better at this — our eval framework at Phenom was partly motivated by the need to make iteration safe at speed — but I still have to consciously slow down when the goal is documentation-first rather than deploy-first.

### "Why this company specifically?"
> Customize per company. Must reference: specific products, use of LLMs/AI in their stack, company stage, or engineering team culture. Never give a generic answer.

## Questions You Should Ask Interviewers

### About the Role
- "What does a typical week look like in this role — is it more model work, infrastructure, or integration?"
- "What would success look like in the first 3-6 months?"
- "What's the hardest unsolved problem the team is working on right now?"

### About the Team
- "How big is the AI/ML team, and how do you split work between research and engineering?"
- "What does the deployment pipeline look like — from a trained model to production?"
- "How do you evaluate model quality before shipping?"

### About Tech & Growth
- "What LLM infrastructure are you running — hosted APIs, self-hosted, or a mix?"
- "Is there scope to shape the architecture, or is the stack mostly locked in?"
- "How does the team stay current with the pace of change in LLMs?"

### About Culture
- "How would you describe the team's culture around production quality vs. speed of shipping?"
- "What do people who thrive here have in common?"
- "What's the balance between working on new capabilities vs. maintaining existing systems?"

## Phone/Video Interview Tips
- Have STAR examples written out (use this file and the `probe:` lines in master.yaml)
- For technical screens: think out loud about tradeoffs, not just solutions
- Ask for clarification if a question is vague — shows precision, not weakness
- It's OK to take 5 seconds before answering behavioral questions
- End with: "Is there anything specific about my background you'd like to dig into further?"

## After the Application

### Follow-Up Etiquette
- If the employer specified a timeline, respect it and wait
- If no timeline was given and 2+ weeks have passed, a brief check-in is acceptable
- Don't call to "stand out" post-submission — it risks a negative impression unless you have genuinely new information

### Thank-You Notes
- After any interview: send a brief thank-you within 24 hours
- 2-3 sentences: appreciation for time + one specific thing discussed that resonated
- Don't use it as a second pitch

## Roleplay Guidelines
When the user asks for interview practice:
1. Ask which role/company to simulate
2. Start with "Tell me about yourself" — use the chatbotCXAgent story as the anchor
3. Progress to role-specific technical questions (LangGraph, fine-tuning, eval)
4. Include 1-2 behavioral questions from the competencies in the job posting
5. End with a tough question ("You don't have a formal CS degree")
6. After each answer, give brief feedback: what worked, what to sharpen
7. Suggest which STAR example fits each question
