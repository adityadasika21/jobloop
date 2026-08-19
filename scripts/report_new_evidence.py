#!/usr/bin/env python3
"""Report the evidence units added today, with their probes.

Run after `jt evidence add` so /ctx answers with what actually landed in
profile/master.yaml rather than a bare "done". The probe is the point of the
reply: it is the question the claim now commits Aditya to answering, and he
should see it while he still remembers what he meant.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from jt.store import load_profile  # noqa: E402


def main() -> int:
    root = pathlib.Path(".")
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    added = [u for u in load_profile(root).get("evidence", [])
             if str(u.get("added_at", "")) == today]

    if not added:
        print("Nothing was added — the context was too vague to make an honest "
              "claim from, or it duplicated something already in the profile.")
        print("Say more about what you actually built and I'll try again.")
        return 0

    for u in added:
        print(f"+ {u['id']}   [{u.get('strength', '?')}]")
        print(" ".join(str(u.get("claim", "")).split()))
        if u.get("metrics"):
            print("metrics: " + ", ".join(f"{k}={v}"
                                          for k, v in u["metrics"].items()))
        print("")
        print(f"PROBE: {' '.join(str(u.get('probe', '')).split())}")
        print("If you can't answer that cold, say so and I'll weaken the claim.")
        print("")
    print("Available to tailoring now. Not on the master resume until you ask.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
