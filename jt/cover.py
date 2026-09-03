"""Cover letters — the third claim surface, after bullets and messages.

Ported from the ai-job-search repo (its cover.cls / Lato + Raleway template)
when the two repos were merged on 2026-09-04. The template is kept verbatim;
what changed is that the letter is now generated from `cover.yaml` and held to
the same provenance rule as everything else:

  * `opening`, every bullet, and `closing` cite evidence ids and go through
    `verify_bullets` — no number or technology the evidence does not support
  * `why_company` is about THEM, not him, so provenance cannot apply — but it
    must list the `sources` (URLs) the company facts were actually checked
    against. A paragraph with company claims and no sources is rejected: the
    old repo's checklist said "verify every company-specific claim" and that
    rule was only ever enforced by hoping.
  * the writing-style rules that are mechanical are mechanical: no em-dashes
    in a letter (his style guide's first rule), and a word budget, because a
    letter that runs to page two has failed before anyone reads it.

Compiled with xelatex — cover.cls needs fontspec — into jobs/<slug>/cover.pdf.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .render import _env, tex_escape
from .store import (
    JobloopError, evidence_index, job_dir, load_job, load_profile, read_yaml,
    write_yaml,
)
from .verify import profile_vocab, verify_bullets

WORD_BUDGET = 320          # body words; the guide says 250-300 is safe, 350 overflows
EM_DASH = "—"
DEFAULT_SIGNOFF = "I look forward to hearing from you."


def paths(root: Path, slug: str) -> tuple[Path, Path, Path]:
    d = job_dir(root, slug)
    return d / "cover.yaml", d / "cover.tex", d / "cover.pdf"


def scaffold(root: Path, slug: str, name: str = "") -> Path:
    from .screen import rank_evidence

    d = job_dir(root, slug)
    job = load_job(root, slug)
    prof = load_profile(root)
    jd = (d / "jd.md").read_text("utf-8") if (d / "jd.md").exists() else ""
    ranked = rank_evidence(prof, jd)[:8]
    data_path, _, _ = paths(root, slug)
    existing = read_yaml(data_path, default={}) if data_path.exists() else {}

    write_yaml(data_path, {
        "_instructions": (
            "Cover letter for this JD, one page. Fill: `greeting` (a named "
            "person if the posting has one, else 'Dear <Company> hiring team,'); "
            "`opening` (2-3 sentences: the role, and the single most relevant "
            "thing actually built — cite evidence); `why_company` (2-3 "
            "sentences about THEM, forward-looking: which of their stated "
            "problems you would work on; every company fact must come from a "
            "URL you fetched, listed in `sources`); 3-5 `bullets` with a bold "
            "`label` and a one-line `text`, each citing evidence; `closing` "
            "(2 sentences: how you work, e.g. gating releases on evals, and "
            "what that means for them — cite evidence). RULES: every number "
            "and technology must be in the cited units; no em-dashes; total "
            f"body under {WORD_BUDGET} words; first person, active voice, no "
            "cliches ('passionate', 'great fit', 'hit the ground running'). "
            "Then: jt verify " + slug + " --cover && jt cover " + slug
        ),
        "contact_name": name or existing.get("contact_name", ""),
        "greeting": existing.get("greeting", ""),
        "company": job.get("company", ""),
        "role": job.get("role", ""),
        "date": existing.get("date", ""),
        "opening": existing.get("opening") or {"text": "", "provenance": []},
        "why_company": existing.get("why_company") or {"text": "", "sources": []},
        "bullets": existing.get("bullets") or [
            {"label": "", "text": "", "provenance": []} for _ in range(4)],
        "closing": existing.get("closing") or {"text": "", "provenance": []},
        "signoff": existing.get("signoff", DEFAULT_SIGNOFF),
        "_candidate_evidence": [
            {"id": u["id"], "claim": " ".join(str(u["claim"]).split()),
             "metrics": u.get("metrics") or {}, "jd_overlap": hits[:10]}
            for u, _s, hits in ranked],
    })
    return data_path


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #

def _words(*texts: str) -> int:
    return sum(len(str(t or "").split()) for t in texts)


def verify_data(prof: dict, data: dict) -> list[str]:
    """Pure check, so a test can feed it a dict. Empty list means clean."""
    evidence = evidence_index(prof)
    vocab = profile_vocab(prof)
    problems: list[str] = []

    opening = data.get("opening") or {}
    closing = data.get("closing") or {}
    bullets = data.get("bullets") or []
    why = data.get("why_company") or {}

    if not str(opening.get("text", "")).strip():
        problems.append("opening: empty")
    if not bullets:
        problems.append("bullets: none — the letter needs 3-5")

    problems += verify_bullets([opening], evidence, label="cover opening", vocab=vocab)
    problems += verify_bullets(
        [{"text": f"{b.get('label', '')}: {b.get('text', '')}".strip(": "),
          "provenance": b.get("provenance") or [],
          "emphasize": b.get("emphasize") or []} for b in bullets],
        evidence, label="cover bullet", vocab=vocab)
    if str(closing.get("text", "")).strip():
        problems += verify_bullets([closing], evidence, label="cover closing", vocab=vocab)

    why_text = str(why.get("text", "")).strip()
    if why_text and not (why.get("sources") or []):
        problems.append(
            "why_company: company-specific claims with no `sources` — list the "
            "URLs you actually fetched, or rephrase in general terms")

    body = [str(opening.get("text", "")), why_text,
            *[f"{b.get('label', '')} {b.get('text', '')}" for b in bullets],
            str(closing.get("text", "")), str(data.get("signoff", ""))]
    for where, text in (("opening", body[0]), ("why_company", why_text),
                        ("closing", body[-2]),
                        *[(f"bullet {i}", t) for i, t in enumerate(body[2:-2], 1)]):
        if EM_DASH in text or " -- " in text:
            problems.append(f"{where}: em-dash — the style guide bans them in "
                            f"letters; use a comma or a full stop")
    n = _words(*body)
    if n > WORD_BUDGET:
        problems.append(f"body is {n} words; budget is {WORD_BUDGET} — a letter "
                        f"that spills to page two has already failed")
    return problems


def verify(root: Path, slug: str) -> list[str]:
    data_path, _, _ = paths(root, slug)
    if not data_path.exists():
        raise JobloopError(
            f"{slug} has no cover.yaml — run `jt cover {slug} --scaffold` and "
            f"have Claude fill it in")
    return verify_data(load_profile(root), read_yaml(data_path))


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def render_tex(root: Path, slug: str) -> str:
    data_path, _, _ = paths(root, slug)
    data = read_yaml(data_path)
    prof = load_profile(root)
    job = load_job(root, slug)
    ident = prof["identity"]
    company = data.get("company") or job.get("company", "")
    greeting = str(data.get("greeting") or "").strip() or (
        f"Dear {data['contact_name']}," if data.get("contact_name")
        else f"Dear {company} hiring team,")
    bullets = [{"label": tex_escape(b.get("label", "")),
                "text": tex_escape(b.get("text", ""))}
               for b in data.get("bullets") or [] if str(b.get("text", "")).strip()]
    ctx = {
        "name": tex_escape(ident["name"]),
        "email": ident["email"],
        "phone": tex_escape(ident["phone"]),
        "linkedin": ident["links"]["linkedin"],
        "company": tex_escape(company),
        "role": tex_escape(data.get("role") or job.get("role", "")),
        "date": tex_escape(data["date"]) if data.get("date") else r"\today",
        "greeting": tex_escape(greeting),
        "opening": tex_escape(" ".join(str(data["opening"]["text"]).split())),
        "why_company": tex_escape(" ".join(
            str((data.get("why_company") or {}).get("text", "")).split())),
        "bullets": bullets,
        "closing": tex_escape(" ".join(
            str((data.get("closing") or {}).get("text", "")).split())),
        "signoff": tex_escape(data.get("signoff") or DEFAULT_SIGNOFF),
    }
    return _env(root).get_template("cover.tex.j2").render(**ctx)


def build_pdf(root: Path, tex_path: Path) -> Path:
    """xelatex, because cover.cls loads fontspec and the bundled Lato/Raleway
    files. Compiled in a temp dir with the class and fonts beside it, so the
    job directory only ever holds cover.tex and cover.pdf."""
    engine = shutil.which("xelatex")
    if not engine:
        raise JobloopError(
            "no xelatex on PATH — commit cover.tex and let GitHub Actions build it")
    tex_path = tex_path.resolve()
    tpl = root / "templates"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copy(tex_path, tmp / tex_path.name)
        shutil.copy(tpl / "cover.cls", tmp / "cover.cls")
        shutil.copytree(tpl / "OpenFonts", tmp / "OpenFonts")
        log = ""
        for _ in range(2):
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
                cwd=tmp, capture_output=True, text=True)
            log = proc.stdout + proc.stderr
        produced = tmp / (tex_path.stem + ".pdf")
        if not produced.exists():
            errs = [l for l in log.splitlines() if l.startswith("!") or "Error" in l][:12]
            raise JobloopError("xelatex failed:\n  " + "\n  ".join(errs or log.splitlines()[-12:]))
        out = tex_path.with_suffix(".pdf")
        shutil.copy(produced, out)
    return out


def page_count(pdf: Path) -> int:
    from .ats import extract_text
    try:
        return extract_text(pdf).count("\f") or 1
    except Exception:
        return 0
