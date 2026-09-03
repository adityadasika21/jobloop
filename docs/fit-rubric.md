# Fit rubric — the judgment layer on top of `jt screen`

`jt screen` scores keyword coverage and the requirement matrix mechanically. It cannot
see culture, travel, seniority feel, or whether the work would *energise* Aditya. This
rubric is what Claude applies after `jt screen`, using `profile/preferences.md` and
`profile/master.yaml`. Write the result to `jobs/<slug>/fit.md`. Merged from the
ai-job-search repo on 2026-09-04.



## Scoring Dimensions

Evaluate each job posting against these five dimensions:

### 1. Technical Skills Match (0-100)
How well do the required/preferred skills align with the candidate's capabilities?

| Score | Meaning |
|-------|---------|
| 80-100 | Core requirements are primary skills |
| 60-79 | Most requirements match, 1-2 gaps that are learnable |
| 40-59 | Partial match, significant upskilling needed |
| 0-39 | Fundamental mismatch |

**Strong match areas:** LangGraph agentic orchestration, LLM fine-tuning (QLoRA/SFT/Unsloth), vLLM serving, Graph RAG, LLM evaluation (pass@k, LLM-judge), Langfuse/LiteLLM observability, PyTorch, ModernBERT/Transformers, FastAPI, Docker, AWS (EC2/S3/SageMaker)
**Moderate match areas:** Classical ML (forecasting, demand modeling), Neo4j knowledge graphs, full-stack (Node.js, React, Firebase), PostgreSQL/MongoDB/Redis
**Weak match areas:** Formal ML research (no PhD; strong applied engineering), Kubernetes/large-scale distributed systems, RL/RLHF (limited direct experience), computer vision

### 2. Experience Match (0-100)
Does work history align with what they're looking for?

| Score | Meaning |
|-------|---------|
| 80-100 | Direct experience in the same domain and role type |
| 60-79 | Related experience, transferable skills clear |
| 40-59 | Adjacent experience, would need to make the case |
| 0-39 | Unrelated experience |

**Strong:** Production LLM/agentic systems (chatbotCXAgent), LLM fine-tuning and serving (Qwen/vLLM), eval framework design, NLU/NLP (ModernBERT multi-task), end-to-end production software delivery (Blueleaves Farms)
**Moderate:** Knowledge graph pipelines (IndexNotes), data-driven forecasting/analytics, backend API design, cloud infrastructure (AWS)
**Entry-level:** Pure ML research roles (no formal research background), roles requiring 5+ years of specialized domain experience

### 3. Behavioral/Culture Fit (0-100)
Does the role and company culture match the behavioral profile?

| Score | Meaning |
|-------|---------|
| 80-100 | Culture strongly matches behavioral preferences |
| 60-79 | Mixed signals but mostly compatible |
| 40-59 | Some friction areas |
| 0-39 | Significant culture mismatch |

**Red flags to research:** Department disorganization, work dominated by maintenance over development, poor chemistry with leadership, culture mismatches. Check reviews, media coverage, LinkedIn connections, and network contacts for insider perspective.

### 4. Location & Logistics (Pass/Fail + Notes)
- Within commute range: PASS
- Remote with occasional office: PASS
- Requires relocation: FAIL (deal-breaker)
- Frequent international travel: FLAG (discuss with user)

### 5. Career Alignment & Motivation (0-100)
Does this role advance career goals and contain tasks that energize?

| Score | Meaning |
|-------|---------|
| 80-100 | Strongly aligned with career direction, clear growth path |
| 60-79 | Good role but only partially aligned with long-term goals |
| 40-59 | Decent job but doesn't build toward career goals |
| 0-39 | Dead end or backwards step |

**Career goals:**
- Build and own production AI/LLM systems end-to-end — model, serving, eval, and integration — at a company where AI is central to the product
- Go deeper on the research-to-production pipeline: stronger understanding of model architecture and training, not just fine-tuning and serving
- Eventually lead a small, high-impact AI/ML team or own an AI platform at a product company

**Motivation filter:** Evaluate not just whether you *can* do the tasks, but whether the tasks will *energize* you. Consider:
- Tasks that energize: designing agentic orchestration, fine-tuning and serving models, building eval frameworks, solving reliability and latency problems in production LLM systems, personal project-style ownership
- Tasks that drain: pure frontend work, maintenance-only roles, heavy process/bureaucracy, roles where AI is peripheral rather than central
- Non-task factors: technical management (not just PM-style), small/fast-moving team, autonomy, role where shipping to production is the measure of success

**Life situation alignment:** Consider personal constraints:
- **Location**: Hyderabad or Bangalore preferred; open to remote roles globally
- **Seniority**: Currently AI/LLM Engineer II at Phenom People — skip junior/entry-level postings
- **Professional development**: Wants to go broader in ML fundamentals and deeper in production AI systems

## Output Format

Present the evaluation as:

```
## Job Fit Evaluation: [Role] at [Company]

| Dimension | Score | Notes |
|-----------|-------|-------|
| Technical Skills | XX/100 | [brief note] |
| Experience Match | XX/100 | [brief note] |
| Behavioral Fit | XX/100 | [brief note] |
| Location | PASS/FAIL | [brief note] |
| Career Alignment | XX/100 | [brief note] |

**Overall Score: XX/100** (weighted average of scored dimensions; report `jt screen`'s fit score beside it — they measure different things)

### Verdict: [Strong Fit / Good Fit / Moderate Fit / Weak Fit / Poor Fit]

### Key Strengths for This Role
- [bullet points]

### Gaps to Address
- [bullet points]

### Recommendation
[1-2 sentences: apply/skip/apply with caveats]

### Company Research Checklist
- [ ] Checked company website (mission, values, recent news)
- [ ] Checked review sites (Glassdoor, AmbitionBox, LinkedIn)
- [ ] Checked LinkedIn for team size, recent hires, connections
- [ ] Checked media for restructuring, growth, or workplace issues
- [ ] Identified network contacts who may know the team/manager
```

## Weighting
- Technical Skills: 30%
- Experience Match: 25%
- Behavioral Fit: 15%
- Career Alignment: 30%

(Location is pass/fail, not weighted)

## Thresholds
- **Strong Fit** (75+): Definitely apply, tailor everything
- **Good Fit** (60-74): Apply, address gaps in cover letter
- **Moderate Fit** (45-59): Consider carefully, discuss with user
- **Weak Fit** (30-44): Probably skip unless strategic reasons
- **Poor Fit** (<30): Skip

## Pre-Application: Call the Employer (Best Practice)

Before writing the application, consider whether the candidate should call the contact person listed in the posting. **Only call if there are substantive questions** - never call just to "be remembered."

### When to Suggest Calling
- The posting has unclear or ambiguous requirements
- It's unclear which competencies are essential vs. nice-to-have
- The role description is vague about day-to-day tasks
- There's a named contact person who invites questions

### Good Questions to Ask
- "What are the primary challenges in this role?"
- "How is time typically divided across the listed responsibilities?"
- "Which competencies are most critical for success in this position?"
- "What does success look like in the first 6-12 months?"

### Rules for the Call
- Prepare a 30-second "elevator pitch" about your background in case they ask
- The call's purpose is **gathering information**, not delivering a pitch
- Take notes - use what you learn to tailor the application
- Reference the conversation naturally in the cover letter ("After speaking with [name], I was especially drawn to...")
