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
from jt.model import stem, tokenize  # noqa: E402
from jt.screen import extract_requirements, match_requirement  # noqa: E402
from jt.store import evidence_index, load_profile  # noqa: E402
from jt.verify import profile_vocab, verify_bullets  # noqa: E402


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


def test_contact_urls_survive_text_extraction(prof):
    """Anchor text of 'GitHub' loses the URL entirely to an ATS parser."""
    text = subprocess.run(
        ["pdftotext", str(ROOT / "profile" / "master-resume.pdf"), "-"],
        capture_output=True, text=True).stdout.lower().replace(" ", "")
    for url in prof["identity"]["links"].values():
        bare = url.replace("https://", "").replace("www.", "").rstrip("/").lower()
        assert bare in text, f"{bare} not recoverable from the PDF"


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

def test_referral_template_is_verbatim():
    """Aditya specified this wording exactly; only the pitch may vary."""
    tpl = (ROOT / "templates" / "referral.md.j2").read_text()
    assert "Hi {{ contact_name }}, hope you're doing well!" in tpl
    assert ("Would you be open to referring me or pointing me to the right "
            "person on the team? Happy to share my resume.") in tpl
    assert tpl.rstrip().endswith("Thanks!\nAditya")
