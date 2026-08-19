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
