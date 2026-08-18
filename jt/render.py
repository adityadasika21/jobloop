"""Rendering: tailored.yaml → resume.tex → resume.pdf, plus the worksheet
that Claude fills in and the referral message.

Jinja is configured with LaTeX-safe delimiters (\\VAR{}, \\BLOCK{}) because
{{ }} and {% %} collide with TeX braces.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .model import utcnow
from .screen import rank_evidence
from .store import (
    JobloopError, evidence_index, job_dir, load_job, load_profile, profile_sha,
    read_text, read_yaml, role_index, write_text, write_yaml,
)

# Single-pass map covering TeX metacharacters AND the unicode the source
# resume uses. One pass matters: escaping first and substituting after would
# turn the "$" of "$\cdot$" into "\$" and print the markup literally.
#
# ATS note — every replacement here must extract back to something a parser
# can read. Math-mode glyphs are avoided for characters that appear inside
# words or contact lines.
_LATEX_MAP = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "–": "--", "—": "---", "’": "'", "‘": "`",
    "“": "``", "”": "''",
    "·": r"\textperiodcentered{}",
    "→": r"$\rightarrow$", "≥": r"$\geq$", "≤": r"$\leq$",
    "•": r"$\bullet$", " ": "~", "…": r"\ldots{}",
}


def tex_escape(s) -> str:
    return "".join(_LATEX_MAP.get(c, c) for c in str(s))


def _env(root: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(root / "templates")),
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string=r"\#{", comment_end_string="}",
        trim_blocks=True, lstrip_blocks=True, autoescape=False,
        undefined=StrictUndefined,
    )
    env.filters["tex"] = tex_escape
    return env


def _fmt_dates(start: str, end: str) -> str:
    """2025-04 / present → 'April 2025 -- Present', matching the source resume."""
    months = ["", "January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]

    def one(v: str) -> str:
        v = str(v or "").strip()
        if not v or v.lower() in ("present", "current", "now"):
            return "Present"
        parts = v.split("-")
        if len(parts) >= 2:
            try:
                return f"{months[int(parts[1])]} {parts[0]}"
            except (ValueError, IndexError):
                pass
        return v
    return f"{one(start)} -- {one(end)}"


# --------------------------------------------------------------------------- #
# Building the render context
# --------------------------------------------------------------------------- #

def _ctx_from_tailored(prof: dict, tailored: dict, root: Path,
                       variant: str) -> dict:
    roles = role_index(prof)
    identity = dict(prof["identity"])
    if tailored.get("headline"):
        identity["headline"] = tailored["headline"]

    experience = []
    for r in tailored.get("experience", []) or []:
        rid = r.get("role_id")
        base = roles.get(rid)
        if not base:
            raise JobloopError(f"tailored.yaml references unknown role_id {rid!r}")
        experience.append({
            "title": tex_escape(r.get("title") or base["title"]),
            "company": tex_escape(base["company"]),
            "location": tex_escape(base.get("location", "")),
            "dates": tex_escape(_fmt_dates(base.get("start"), base.get("end"))),
            "bullets": [{"text": tex_escape(b["text"])}
                        for b in (r.get("bullets") or [])],
        })

    projects = []
    for p in tailored.get("projects", []) or []:
        stack = p.get("stack") or []
        projects.append({
            "name": tex_escape(p.get("name", "")),
            "stack": tex_escape(", ".join(stack) if isinstance(stack, list) else stack),
            "bullets": [{"text": tex_escape(b["text"])}
                        for b in (p.get("bullets") or [])],
        })

    groups = tailored.get("skill_groups") or prof["skill_groups"]
    skill_groups = [{"name": tex_escape(g["name"]),
                     "items_line": tex_escape(", ".join(g["items"]))}
                    for g in groups if g.get("items")]

    education = [{
        "institution": tex_escape(e["institution"]),
        "location": tex_escape(e.get("location", "")),
        "degree": tex_escape(e["degree"]),
        "dates": tex_escape(_fmt_dates(e.get("start"), e.get("end"))),
    } for e in prof.get("education", [])]

    # ATS parsers read extracted TEXT, not link targets. Anchor text of
    # "GitHub" loses the URL entirely, so the visible text is the bare URL.
    links = identity["links"]
    display = {k: re.sub(r"^https?://(www\.)?", "", str(v)).rstrip("/")
               for k, v in links.items()}

    return {
        "identity": {k: (tex_escape(v) if isinstance(v, str) else v)
                     for k, v in identity.items()} | {"links": links},
        "display": {k: tex_escape(v) for k, v in display.items()},
        "experience": experience,
        "projects": projects,
        "skill_groups": skill_groups,
        "education": education,
        "meta": {"profile_sha": profile_sha(root), "variant": variant,
                 "generated_at": utcnow()},
    }


def master_tailored(prof: dict) -> dict:
    """The untailored master resume, expressed in tailored.yaml's own shape.

    Used by `jt build --master` to prove the pipeline reproduces the original
    PDF before any tailoring logic is trusted.
    """
    by_role: dict[str, list[dict]] = {}
    projects: dict[str, dict] = {}
    for u in prof["evidence"]:
        item = {"text": " ".join(str(u["claim"]).split()), "provenance": [u["id"]]}
        if u.get("kind") == "project":
            parent = u.get("parent")
            if parent:
                projects.setdefault(parent, {"bullets": []})["bullets"].append(item)
            else:
                projects.setdefault(u["id"], {"bullets": []}).update(
                    {"name": u.get("name", u["id"]), "stack": u.get("stack", [])}
                )
                projects[u["id"]].setdefault("bullets", []).insert(0, item)
        else:
            by_role.setdefault(u["role"], []).append(item)

    experience = [{"role_id": r["id"], "bullets": by_role.get(r["id"], [])}
                  for r in prof["roles"]]
    proj_list = [p for p in projects.values() if p.get("name")]
    return {
        "headline": prof["identity"]["headline"],
        "experience": experience,
        "projects": proj_list,
        "skill_groups": prof["skill_groups"],
    }


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #

def render_tex(root: Path, tailored: dict, variant: str) -> str:
    prof = load_profile(root)
    ctx = _ctx_from_tailored(prof, tailored, root, variant)
    return _env(root).get_template("resume.tex.j2").render(**ctx)


def build_pdf(tex_path: Path, out_pdf: Path | None = None,
              keep_logs: bool = False) -> Path:
    """Compile with pdflatex. Two passes for hyperref refs."""
    engine = shutil.which("pdflatex") or shutil.which("lualatex")
    if not engine:
        raise JobloopError(
            "no pdflatex on PATH — commit the .tex and let GitHub Actions build it"
        )
    tex_path = tex_path.resolve()
    cls = tex_path.parent / "resume.cls"
    if not cls.exists():
        raise JobloopError(f"resume.cls not found next to {tex_path.name}")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copy(tex_path, tmp / tex_path.name)
        shutil.copy(cls, tmp / "resume.cls")
        log = ""
        for _ in range(2):
            proc = subprocess.run(
                [engine, "-interaction=nonstopmode", "-halt-on-error",
                 tex_path.name],
                cwd=tmp, capture_output=True, text=True,
            )
            log = proc.stdout + proc.stderr
        produced = tmp / (tex_path.stem + ".pdf")
        if not produced.exists():
            errs = [l for l in log.splitlines()
                    if l.startswith("!") or "Error" in l][:12]
            raise JobloopError(
                "pdflatex failed:\n  " + "\n  ".join(errs or log.splitlines()[-12:])
            )
        out_pdf = out_pdf or tex_path.with_suffix(".pdf")
        shutil.copy(produced, out_pdf)
        if keep_logs:
            shutil.copy(tmp / (tex_path.stem + ".log"),
                        out_pdf.with_suffix(".log"))
    return out_pdf


def write_job_tex(root: Path, slug: str) -> Path:
    d = job_dir(root, slug)
    tailored = read_yaml(d / "tailored.yaml")
    tex = render_tex(root, tailored, variant=slug)
    out = d / "resume.tex"
    write_text(out, tex)
    # Actions and local builds both need the class beside the .tex.
    shutil.copy(root / "templates" / "resume.cls", d / "resume.cls")
    return out


# --------------------------------------------------------------------------- #
# Worksheet — what Claude fills in
# --------------------------------------------------------------------------- #

def worksheet(root: Path, slug: str, top: int = 14) -> Path:
    """Emit tailoring.worksheet.yaml: the JD's asks next to the best TRUE
    material, ranked. Claude writes tailored.yaml from this."""
    prof = load_profile(root)
    d = job_dir(root, slug)
    job = load_job(root, slug)
    jd_text = read_text(d / "jd.md")
    ranked = rank_evidence(prof, jd_text)

    from .screen import extract_requirements, match_requirement
    reqs = extract_requirements(jd_text)

    ws = {
        "_instructions": (
            "Write tailored.yaml from this worksheet. RULES: (1) every bullet "
            "needs `provenance: [evidence-id]`; (2) never state a number that "
            "is not in the cited unit's claim/metrics; (3) never name a "
            "technology the cited units don't mention; (4) rephrase in the "
            "JD's vocabulary but do not upgrade scope, seniority, or ownership; "
            "(5) unmatched requirements stay gaps — report them, don't invent. "
            "Run `jt verify " + slug + "` until clean."
        ),
        "job": {"company": job.get("company"), "role": job.get("role"),
                "url": job.get("url"), "work_mode": job.get("work_mode")},
        "requirements": [
            match_requirement(r["text"], prof) | {"kind": r["kind"]}
            for r in reqs
        ],
        "known_gaps": prof.get("known_gaps", []),
        "evidence_ranked": [
            {"id": u["id"],
             "score": score,
             "strength": u.get("strength"),
             "role": u.get("role") or u.get("kind"),
             "claim": " ".join(str(u["claim"]).split()),
             "metrics": u.get("metrics") or {},
             "allowed_skills": u.get("skills", []),
             "jd_overlap": hits[:12],
             "probe": u.get("probe", "")}
            for u, score, hits in ranked[:top]
        ],
        "skill_inventory": prof["skill_groups"],
    }
    out = d / "tailoring.worksheet.yaml"
    write_yaml(out, ws)
    return out


def render_referral(root: Path, slug: str) -> str:
    """Fixed-format LinkedIn referral ask. Only the pitch paragraph varies."""
    d = job_dir(root, slug)
    job = load_job(root, slug)
    data = read_yaml(d / "referral.yaml", default={})
    if not data.get("pitch"):
        raise JobloopError(
            f"{slug}: referral.yaml has no `pitch`. Run `jt referral {slug} "
            f"--scaffold` and have Claude write the 2-4 sentence paragraph."
        )
    env = Environment(loader=FileSystemLoader(str(root / "templates")),
                      trim_blocks=False, lstrip_blocks=False, autoescape=False)
    tpl = env.get_template("referral.md.j2")
    return tpl.render(
        contact_name=data.get("contact_name") or "[Name]",
        role=data.get("role") or job.get("role", "[Role]"),
        company=data.get("company") or job.get("company", "[Company]"),
        pitch=" ".join(str(data["pitch"]).split()),
    )
