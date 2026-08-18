#!/usr/bin/env python3
"""Print the slugs that are actually ready to tailor, newest-fit first.

A job created from an application email has no JD text, so there is nothing to
tailor against — those must be skipped rather than half-tailored from a
confirmation email. Used by .github/workflows/tailor.yml.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jt.db import query           # noqa: E402
from jt.store import repo_root    # noqa: E402

NO_JD = "no JD text"


def main(limit: int = 3) -> int:
    root = repo_root(Path(__file__).resolve().parent)
    rows = query(root, """
        SELECT slug, COALESCE(fit_score, 50) AS fit
        FROM jobs
        WHERE status IN ('queued', 'analyzed')
        ORDER BY fit DESC
    """)
    out = []
    for r in rows:
        jd = root / "jobs" / r["slug"] / "jd.md"
        if not jd.exists():
            continue
        head = jd.read_text(encoding="utf-8")[:400]
        if NO_JD in head or len(jd.read_text(encoding="utf-8")) < 300:
            continue
        if (root / "jobs" / r["slug"] / "tailored.yaml").exists():
            continue
        out.append(r["slug"])
    print(" ".join(out[:limit]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 3))
