"""The guarantees that must never silently regress.

These aren't unit tests for their own sake. Each one pins a property the whole
system's value depends on — if `jt verify` stops catching an inflated metric,
every resume it produces becomes a liability rather than an asset.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

from jt.ats import find_collisions  # noqa: E402
from jt.evidence import (  # noqa: E402
    add as evidence_add, validate as evidence_validate, warnings as evidence_warnings)
from jt.message import TYPES, resolve_type  # noqa: E402
from jt.model import stem, tokenize  # noqa: E402
from jt.render import emphasis_terms, tex_escape_emph  # noqa: E402
from jt.screen import extract_requirements, match_requirement  # noqa: E402
from jt.store import evidence_index, load_profile  # noqa: E402
from jt.verify import profile_vocab, verify_bullets, verify_profile  # noqa: E402


@pytest.fixture(scope="module")
def prof():
    return load_profile(ROOT)


@pytest.fixture(scope="module")
def ev(prof):
    return evidence_index(prof)


@pytest.fixture(scope="module")
def vocab(prof):
    return profile_vocab(prof)


# --------------------------------------------------------------------------- #
# 1. Anti-fabrication
# --------------------------------------------------------------------------- #

def test_clean_bullet_passes(ev, vocab):
    bullets = [{
        "text": "Engineered tool-calling agents under XGrammar constrained "
                "decoding, raising tool-routing accuracy to 91.9%.",
        "provenance": ["ev-phenom-toolcalling-guardrails"],
    }]
    assert verify_bullets(bullets, ev, vocab=vocab) == []


def test_inflated_metric_is_caught(ev, vocab):
    """The highest-consequence fabrication: a real claim with a better number."""
    bullets = [{
        "text": "Raised tool-routing accuracy to 99.4%.",
        "provenance": ["ev-phenom-toolcalling-guardrails"],
    }]
    problems = verify_bullets(bullets, ev, vocab=vocab)
    assert any("99.4%" in p for p in problems)


def test_invented_technology_is_caught(ev, vocab):
    bullets = [{
        "text": "Served Qwen models on vLLM and Kubernetes at 10.98 RPS.",
        "provenance": ["ev-phenom-finetune-serving"],
    }]
    problems = verify_bullets(bullets, ev, vocab=vocab)
    assert any("Kubernetes" in p for p in problems)


def test_missing_provenance_is_caught(ev, vocab):
    bullets = [{"text": "Led a team of ten engineers.", "provenance": []}]
    problems = verify_bullets(bullets, ev, vocab=vocab)
    assert any("NO PROVENANCE" in p for p in problems)


def test_unknown_evidence_id_is_caught(ev, vocab):
    bullets = [{"text": "Did a thing.", "provenance": ["ev-does-not-exist"]}]
    problems = verify_bullets(bullets, ev, vocab=vocab)
    assert any("unknown evidence" in p for p in problems)


def test_sentence_initial_capital_is_not_a_technology(ev, vocab):
    """Regression: 'That maps closely to...' was flagged as invented tooling."""
    bullets = [{
        "text": "Built the evaluation harness gating releases across all 12 "
                "nodes. That work covered pass@k rubrics.",
        "provenance": ["ev-phenom-eval-framework"],
    }]
    assert verify_bullets(bullets, ev, vocab=vocab) == []


def test_real_job_title_words_are_allowed(ev, vocab):
    """Regression: 'Engineer' failed because no evidence claim contains it."""
    bullets = [{
        "text": "LLM Engineer working on multi-agent systems on LangGraph.",
        "provenance": ["ev-phenom-chatbotcx-architecture"],
    }]
    assert verify_bullets(bullets, ev, vocab=vocab) == []


def test_seniority_inflation_is_still_caught(ev, vocab):
    """The flip side: title words are allowed only if a real role has them."""
    bullets = [{
        "text": "Worked as Principal Architect on LangGraph systems.",
        "provenance": ["ev-phenom-chatbotcx-architecture"],
    }]
    problems = verify_bullets(bullets, ev, vocab=vocab)
    assert any("Principal" in p for p in problems)


# --------------------------------------------------------------------------- #
# 2. JD parsing
# --------------------------------------------------------------------------- #

JD = """\
Senior LLM Engineer at Acme

Requirements
- 3+ years of software engineering experience, with at least 2 years building
  production machine learning systems
- Experience with agentic frameworks such as LangChain, LangGraph, or DSPy
- Kubernetes and service mesh experience

Nice to have
- Experience fine-tuning open-source models

What you will do
- Ship multi-agent workflows
"""


def test_requirement_bullets_are_not_mistaken_for_headings():
    """Regression: bullets containing 'experience' matched the section-heading
    regex, silently dropping the entire requirements block."""
    reqs = extract_requirements(JD)
    texts = " ".join(r["text"] for r in reqs)
    assert "3+ years" in texts
    assert "agentic frameworks" in texts


def test_wrapped_requirement_lines_are_joined():
    reqs = extract_requirements(JD)
    first = next(r for r in reqs if r["text"].startswith("3+ years"))
    assert "production machine learning systems" in first["text"]


def test_requirement_kinds_are_separated():
    kinds = {r["kind"] for r in extract_requirements(JD)}
    assert {"required", "nice_to_have", "responsibility"} <= kinds


def test_known_gap_does_not_veto_real_evidence(prof):
    """'LangChain, LangGraph, or DSPy' is MET — two of three are shipped —
    even though DSPy is a known gap. The gap rides along as a caveat."""
    m = match_requirement(
        "Experience with agentic frameworks such as LangChain, LangGraph, or DSPy",
        prof)
    assert m["status"] == "met"
    assert m["caveat"] and "dspy" in m["caveat"]


def test_genuine_gap_is_still_a_gap(prof):
    m = match_requirement("Kubernetes and service mesh experience", prof)
    assert m["status"] == "gap"


def test_role_domain_counts_as_domain_experience(prof):
    """Work at an HR-tech company IS HR-tech experience."""
    m = match_requirement("Experience in HR tech or recruitment domain", prof)
    assert m["status"] in ("met", "partial")


# --------------------------------------------------------------------------- #
# 3. Rendering / ATS
# --------------------------------------------------------------------------- #

def test_master_resume_builds_to_one_clean_page(tmp_path):
    out = subprocess.run(
        ["python", "-m", "jt.cli", "build", "--master"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    pdf = ROOT / "profile" / "master-resume.pdf"
    assert pdf.exists()
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    assert "Pages:           1" in info


def test_built_resume_has_no_colliding_text():
    """Regression: tightening list leading overlapped bullets onto headings.
    Text extraction cannot see this, so only the geometry check catches it."""
    pdf = ROOT / "profile" / "master-resume.pdf"
    assert find_collisions(pdf) == []


def test_no_template_leakage_in_pdf():
    """Regression: `group.items` resolved to dict.items and printed
    '<built-in method items ...>' into the skills section."""
    text = subprocess.run(
        ["pdftotext", str(ROOT / "profile" / "master-resume.pdf"), "-"],
        capture_output=True, text=True).stdout
    for bad in ("built-in method", "object at 0x", "Undefined", "\\VAR{"):
        assert bad not in text


def test_contact_links_render_in_the_chosen_style(prof):
    """Every link must reach the page in the form the profile asked for.

    Aditya chose anchor text on 2026-08-19, knowing the cost: a parser gets
    the word "GitHub" and the address is gone. That is a decision, not a bug,
    so the test pins the CHOICE rather than one of the two options — flip
    `identity.link_style` to `bare` and this still passes, on the URLs.
    """
    ident = prof["identity"]
    text = subprocess.run(
        ["pdftotext", str(ROOT / "profile" / "master-resume.pdf"), "-"],
        capture_output=True, text=True).stdout.lower()
    squashed = text.replace(" ", "")
    anchor = str(ident.get("link_style", "bare")).lower() == "anchor"
    for key, url in ident["links"].items():
        if anchor:
            label = str((ident.get("link_labels") or {}).get(key, key)).lower()
            assert label in text, f"{key}: anchor {label!r} missing from the PDF"
        else:
            bare = url.replace("https://", "").replace("www.", "").rstrip("/").lower()
            assert bare in squashed, f"{bare} not recoverable from the PDF"


def test_pdf_carries_the_ats_unicode_map():
    r"""`\input{glyphtounicode}` + `\pdfgentounicode=1` is what makes pdfLaTeX
    output reliably text-extractable. It was missing from the reconstructed
    class entirely — extraction happened to work, which is not the same as
    working. Highest-value single line in the class."""
    cls = (ROOT / "templates" / "resume.cls").read_text()
    assert "\\input{glyphtounicode}" in cls
    assert "\\pdfgentounicode=1" in cls


@pytest.mark.parametrize("fragment", [
    "\\LoadClass[letterpaper,10pt]{article}",       # his 10pt, not 11pt
    "\\addtolength{\\textwidth}{1in}",                # his margins
    "\\addtolength{\\textheight}{1.0in}",
    "leftmargin=0.15in",                            # his list indent
    "0.97\\textwidth",                              # his tabular width
])
def test_class_matches_the_authoritative_source(fragment):
    """reference/resume-source.tex is Aditya's own file. Where the
    reverse-engineered class disagreed with it, his won — and it stays won."""
    src = (ROOT / "reference" / "resume-source.tex").read_text()
    cls = (ROOT / "templates" / "resume.cls").read_text()
    assert fragment in cls
    assert fragment.replace("\\LoadClass[", "\\documentclass[") in src or fragment in src


# --------------------------------------------------------------------------- #
# 3b. Emphasis is a claim
# --------------------------------------------------------------------------- #

def test_emphasis_is_provenance_bound(ev, vocab):
    """Bold says 'this is the part that matters'. A model may no more invent
    it than invent the claim itself."""
    problems = verify_bullets([{
        "text": "Engineered tool-calling agents under XGrammar constrained decoding.",
        "provenance": ["ev-phenom-toolcalling-guardrails"],
        "emphasize": ["Kubernetes"],
    }], ev, vocab=vocab)
    assert any("Kubernetes" in p for p in problems)


def test_supported_emphasis_passes(ev, vocab):
    assert verify_bullets([{
        "text": "Engineered tool-calling agents under XGrammar constrained decoding.",
        "provenance": ["ev-phenom-toolcalling-guardrails"],
        "emphasize": ["XGrammar"],
    }], ev, vocab=vocab) == []


def test_profile_emphasis_terms_can_actually_match(prof):
    """An `emphasize` entry that appears nowhere in its own unit would fail
    silently forever, by simply never matching."""
    assert verify_profile(prof) == []


def test_emphasis_bolds_whole_tokens_only():
    out = tex_escape_emph("RAG and Graph RAG retrieval", ["Graph RAG"])
    assert out == "RAG and \\textbf{Graph RAG} retrieval"


def test_longest_emphasis_term_wins():
    """'RAG' must not eat the front of 'Graph RAG'."""
    terms = emphasis_terms([{"emphasize": ["RAG", "Graph RAG"]}])
    assert terms[0] == "Graph RAG"
    assert tex_escape_emph("Graph RAG retrieval", terms) == \
        "\\textbf{Graph RAG} retrieval"


def test_master_resume_bolds_the_load_bearing_terms():
    """His hand-written page bolds the system, the framework and the one
    number worth arguing about; the generated one read flat beside it."""
    tex = (ROOT / "profile" / "master-resume.tex").read_text()
    for term in ("chatbotCXAgent", "LangGraph", "Graph RAG", "QLoRA", "vLLM",
                 "ModernBERT", "LLM orchestration engine"):
        assert "\\textbf{" + term + "}" in tex, f"{term} is not emphasised"


# --------------------------------------------------------------------------- #
# 4. Keyword machinery
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("plural,singular", [
    ("pipelines", "pipeline"), ("releases", "release"),
    ("harnesses", "harness"), ("models", "model"), ("systems", "system"),
])
def test_plurals_fold_onto_singulars(plural, singular):
    """Regression: a blanket 'es' strip made pipelines != pipeline, so every
    plural in a JD looked like a missing keyword."""
    assert stem(plural) == stem(singular)


def test_jd_filler_is_not_scored_as_a_keyword():
    toks = tokenize("Comfortable with familiarity and a proven track record")
    assert not ({"comfortable", "familiarity", "proven", "record"} & toks)


# --------------------------------------------------------------------------- #
# 5. Referral format is fixed
# --------------------------------------------------------------------------- #

def test_every_message_type_has_a_template():
    for name, spec in TYPES.items():
        assert (ROOT / "templates" / spec["template"]).exists(), name


@pytest.mark.parametrize("mtype", sorted(TYPES))
def test_message_formats_are_fixed(mtype):
    """One paragraph varies. Everything around it is Aditya's wording and is
    reproduced verbatim — including the sign-off, which is how he signs."""
    tpl = (ROOT / "templates" / TYPES[mtype]["template"]).read_text()
    assert "{{ pitch }}" in tpl, f"{mtype}: nothing varies"
    assert tpl.rstrip().endswith("Thanks!\nAditya"), f"{mtype}: wrong sign-off"


def test_message_type_prefixes_resolve():
    """Discord sends whatever the user picked; `follow` must reach follow-up."""
    assert resolve_type("follow") == "follow-up"
    assert resolve_type("") == "referral"


def test_a_follow_up_never_counts_the_days():
    """The one thing that turns a follow-up into a complaint."""
    tpl = (ROOT / "templates" / "messages" / "follow-up.md.j2").read_text()
    body = tpl.split("#}", 1)[1]
    for phrase in ("weeks ago", "haven't heard", "have not heard",
                   "still waiting", "any update yet"):
        assert phrase not in body.lower()


# --------------------------------------------------------------------------- #
# 6. Mail sync cannot duplicate a job
# --------------------------------------------------------------------------- #

def test_a_known_thread_cannot_create_a_second_job(tmp_path):
    """Regression: dedup covered repeat EVENTS but not repeat job CREATION.

    A later message on an already-filed thread guessed the role slightly
    differently, so match_job scored it below threshold and auto-intake made a
    second Barclays stub. The thread id alone must be enough to prevent that.
    """
    import shutil

    from jt.mail import ingest
    from jt.store import save_job

    shutil.copytree(ROOT / "profile", tmp_path / "profile")
    slug = "2026-08-18-barclays-senior-engineer-ai-platform"
    (tmp_path / "jobs" / slug).mkdir(parents=True)
    save_job(tmp_path, slug, {
        "company": "Barclays", "role": "Senior Engineer, AI Platform",
        "status": "applied", "source": "email",
        "events": [{"ts": "2026-08-10T00:00:00Z", "kind": "applied",
                    "detail": "application received", "source": "gmail:abc123",
                    "ref": "abc123"}],
    })

    # Same thread, a role string that will not match the tracked one.
    res = ingest(tmp_path, [{
        "thread_id": "abc123",
        "from": "no-reply@barclays.com",
        "subject": "Your application for the Vice President position",
        "body": "Thank you for applying to Barclays. Your application for the "
                "Vice President position is in review.",
        "date": "2026-08-14T00:00:00Z",
    }], auto_intake=True)

    assert res["created"] == [], "a filed thread created a second job"
    assert res["matched"] == 1


def test_referral_template_is_verbatim():
    """Aditya specified this wording exactly; only the pitch may vary."""
    tpl = (ROOT / "templates" / "referral.md.j2").read_text()
    assert "Hi {{ contact_name }}, hope you're doing well!" in tpl
    assert ("Would you be open to referring me or pointing me to the right "
            "person on the team? Happy to share my resume.") in tpl
    assert tpl.rstrip().endswith("Thanks!\nAditya")


# --------------------------------------------------------------------------- #
# 7. Adding evidence cannot corrupt the root of trust
# --------------------------------------------------------------------------- #

@pytest.fixture
def sandbox(tmp_path):
    """A throwaway repo whose master.yaml is the real one."""
    import shutil
    (tmp_path / "profile").mkdir()
    shutil.copy(ROOT / "profile" / "master.yaml", tmp_path / "profile" / "master.yaml")
    return tmp_path


GOOD = {
    "id": "ev-test-rate-limiter",
    "role": "phenom-ai-llm-eng-ii",
    "claim": "Built a rate limiter for the agent gateway, cutting p99 latency "
             "from 3s to 400ms under burst load.",
    "skills": ["rate-limiting", "latency-optimization"],
    "metrics": {"p99_before": "3s", "p99_after": "400ms"},
    "keywords": ["rate limiting", "latency", "throughput"],
    "strength": "strong",
    "probe": "What algorithm, and what was saturating at 3s?",
}


def test_evidence_add_preserves_every_comment(sandbox):
    before = (sandbox / "profile" / "master.yaml").read_text()
    assert evidence_add(sandbox, [dict(GOOD)]) == ["ev-test-rate-limiter"]
    after = (sandbox / "profile" / "master.yaml").read_text()
    # A YAML round-trip would strip these, taking the rules with them.
    for comment in ("# RULE: Nothing may appear on a generated resume",
                    "# KNOWN GAPS", "# emphasize  —"):
        assert comment in after, f"lost {comment!r}"
    assert len(after) > len(before)


def test_added_evidence_is_tailorable_but_not_on_the_master_resume(sandbox):
    from jt.store import load_profile
    evidence_add(sandbox, [dict(GOOD)])
    unit = {u["id"]: u for u in load_profile(sandbox)["evidence"]}["ev-test-rate-limiter"]
    assert unit["on_master"] is False
    assert unit["added_at"]


def test_evidence_records_where_the_claim_came_from(sandbox):
    from jt.store import load_profile
    evidence_add(sandbox, [dict(GOOD)], source_note="built a rate limiter, 3s -> 400ms")
    unit = {u["id"]: u for u in load_profile(sandbox)["evidence"]}["ev-test-rate-limiter"]
    assert "rate limiter" in unit["source_note"]


def test_evidence_without_a_probe_is_rejected(prof):
    bad = dict(GOOD, probe="")
    assert any("probe" in p for p in evidence_validate(prof, bad))


def test_probe_must_be_a_question(prof):
    bad = dict(GOOD, probe="Ask about the algorithm.")
    assert any("question" in p for p in evidence_validate(prof, bad))


def test_number_not_in_metrics_warns_but_does_not_block(prof):
    """A number the metrics map doesn't hold should be flagged — but not
    rejected. A check that refuses a true claim teaches people to edit
    master.yaml by hand instead, which is strictly worse."""
    loose = dict(GOOD, claim=GOOD["claim"] + " Sustained 12k requests per minute.")
    assert evidence_validate(prof, loose) == []
    assert any("12k" in w for w in evidence_warnings(loose))


def test_a_name_with_digits_in_it_is_not_a_metric(prof):
    """p99, GPT-4.1, g5.xlarge. Flagging these would make the warning noise,
    and a warning that is always wrong is a warning nobody reads."""
    assert not any("metrics" in w for w in evidence_warnings(dict(GOOD)))


def test_duplicate_id_is_rejected(prof):
    bad = dict(GOOD, id="ev-phenom-eval-framework")
    assert any("already exists" in p for p in evidence_validate(prof, bad))


def test_unknown_role_is_rejected(prof):
    bad = dict(GOOD, role="ev-nope")
    assert any("not a role" in p for p in evidence_validate(prof, bad))


def test_a_rejected_unit_leaves_master_yaml_untouched(sandbox):
    from jt.store import JobloopError
    before = (sandbox / "profile" / "master.yaml").read_text()
    with pytest.raises(JobloopError):
        evidence_add(sandbox, [dict(GOOD, probe="")])
    assert (sandbox / "profile" / "master.yaml").read_text() == before


# --------------------------------------------------------------------------- #
# 8. Free text has to reach the right job
#
# The failure this pins: a whole sentence went into /jobstatus's `job` field
# and came back "no job matching 'auric ai round 1 done. Waiting for
# feedback...'". Two bugs in one — the matcher only did substring containment,
# so it could not read a sentence, and it could not even match "auric ai"
# against the slug `auricai` because of the space.
# --------------------------------------------------------------------------- #

@pytest.fixture
def jobsbox(tmp_path):
    from jt.store import save_job
    (tmp_path / "profile").mkdir()
    (ROOT / "profile" / "master.yaml").read_bytes()  # sanity: repo intact
    import shutil
    shutil.copy(ROOT / "profile" / "master.yaml", tmp_path / "profile" / "master.yaml")
    for slug, company, role in [
        ("2026-08-18-auricai-applied-ai-engineer", "Auricai", "Applied AI Engineer"),
        ("2026-08-18-joveo-ai-llm-engineer", "Joveo AI", "LLM Engineer"),
        ("2026-08-18-eightfold-ai-ml-engineer-nlp-ai", "Eightfold AI", "ML Engineer – NLP/AI"),
        ("2026-08-18-eightfold-senior-engineer-fullstack", "Eightfold", "Senior Engineer- Fullstack"),
        ("2026-08-18-wissen-technology-ai-engineer-rag-llm-systems",
         "Wissen Technology", "AI Engineer – RAG & LLM Systems"),
    ]:
        (tmp_path / "jobs" / slug).mkdir(parents=True)
        save_job(tmp_path, slug, {"company": company, "role": role,
                                  "status": "applied", "events": []})
    return tmp_path


def test_a_sentence_resolves_to_the_job_it_names(jobsbox):
    """The exact string that failed in Discord."""
    from jt.store import resolve_slug
    said = ("auric ai round 1 done. Waiting for feedback. Question was on RAG "
            "and entity resolution and grouping entities. Answered fine overall")
    assert resolve_slug(jobsbox, said) == "2026-08-18-auricai-applied-ai-engineer"


def test_a_company_typed_with_a_space_resolves(jobsbox):
    """`auric ai` must reach the slug `auricai`. Nobody knows how a name was
    slugified, and they should not have to."""
    from jt.store import resolve_slug
    assert resolve_slug(jobsbox, "auric ai") == "2026-08-18-auricai-applied-ai-engineer"


def test_rag_in_the_sentence_does_not_beat_the_company_name(jobsbox):
    """"RAG" appears in the Wissen role title. A word that identifies one job
    must outweigh a word that merely appears in one."""
    from jt.store import rank_jobs
    ranked = rank_jobs(jobsbox, "auric ai round 1, they asked about RAG")
    assert ranked[0][0] == "2026-08-18-auricai-applied-ai-engineer"
    assert ranked[0][1] > ranked[1][1] * 1.4


def test_two_jobs_at_one_company_still_refuse_to_guess(jobsbox):
    """Guessing here writes an interview onto the wrong timeline."""
    from jt.store import JobloopError, resolve_slug
    with pytest.raises(JobloopError, match="ambiguous"):
        resolve_slug(jobsbox, "eightfold")


def test_words_every_job_shares_identify_nothing(jobsbox):
    from jt.store import JobloopError, resolve_slug
    with pytest.raises(JobloopError):
        resolve_slug(jobsbox, "the ai engineer role")


def test_unrelated_text_resolves_to_nothing(jobsbox):
    from jt.store import JobloopError, resolve_slug
    with pytest.raises(JobloopError, match="no job matching"):
        resolve_slug(jobsbox, "what is the weather tomorrow")


def test_an_exact_slug_still_wins(jobsbox):
    from jt.store import resolve_slug
    slug = "2026-08-18-joveo-ai-llm-engineer"
    assert resolve_slug(jobsbox, slug) == slug


# --------------------------------------------------------------------------- #
# 9. The inbox is the handoff to the routine
#
# There is no ANTHROPIC_API_KEY in Actions and there is not going to be one:
# judgment runs on the workstation, on a subscription, on a timer. So a
# workflow's job is to do the deterministic half and leave the rest here.
# --------------------------------------------------------------------------- #

def test_a_request_survives_the_round_trip(tmp_path):
    from jt.inbox import add, pending, done
    add(tmp_path, "freetext", text="auric ai round 1 done", channel_id="123")
    items = pending(tmp_path)
    assert len(items) == 1
    assert items[0]["kind"] == "freetext"
    assert items[0]["channel_id"] == "123"
    done(tmp_path, items[0]["id"])
    assert pending(tmp_path) == []


def test_two_requests_in_the_same_second_both_survive(tmp_path):
    """Discord bursts. Losing the second message would be silent."""
    from jt.inbox import add, pending
    add(tmp_path, "freetext", text="first")
    add(tmp_path, "freetext", text="second")
    assert len({i["id"] for i in pending(tmp_path)}) == 2


def test_unknown_kind_is_refused(tmp_path):
    from jt.inbox import add
    from jt.store import JobloopError
    with pytest.raises(JobloopError, match="unknown inbox kind"):
        add(tmp_path, "nonsense", text="x")


def test_empty_inbox_is_empty(tmp_path):
    from jt.inbox import pending
    assert pending(tmp_path) == []


def test_the_discord_workflow_does_no_thinking():
    """Regression on a design error: these handlers were first written around
    claude-code-action, which can never run — there is no API key and the
    routine is what does judgment."""
    wf = (ROOT / ".github" / "workflows" / "discord.yml").read_text()
    assert "claude-code-action" not in wf
    assert "secrets.ANTHROPIC_API_KEY" not in wf


def test_the_routine_drains_the_inbox_before_anything_else():
    prompt = (ROOT / "scripts" / "routine-prompt.md").read_text()
    assert "## 1. Drain the inbox" in prompt
    assert prompt.index("## 1. Drain the inbox") < prompt.index("## 2. Tailor")


def test_inbox_detail_is_not_read_on_an_idle_run():
    """The hourly routine reads routine-prompt.md every run and most runs have
    an empty inbox. Paying for 70 lines about requests that are not there is a
    cost with no upside, so the detail lives in a file read on demand."""
    prompt = (ROOT / "scripts" / "routine-prompt.md").read_text()
    detail = (ROOT / "scripts" / "inbox-handling.md").read_text()
    for kind in ("freetext", "context", "message"):
        assert f"kind: {kind}" in detail
        assert f"kind: {kind}" not in prompt
    assert "inbox-handling.md" in prompt


def test_the_worker_is_locked_and_gated():
    """The gate is the expensive question answered cheaply: an idle repo must
    not start a model. Both timers call this one script, so the check lives
    here or nowhere."""
    body = (ROOT / "scripts" / "run-routine.sh").read_text()
    assert ".jobloop.lock" in body and "flock" in body
    gate = body.index("jt work")
    assert gate < body.index("claude -p"), "Claude starts before the gate"


def test_gmail_is_not_a_heartbeat():
    """Sweeping Gmail on a schedule was the only reason a quiet repo ever
    woke up. It is a request now."""
    prompt = (ROOT / "scripts" / "routine-prompt.md").read_text()
    assert "ONLY on request" in prompt
    assert "kind: mail" in (ROOT / "scripts" / "inbox-handling.md").read_text()
