#!/usr/bin/env python3
"""Post text to Discord through the existing bot service.

Reads the message on stdin. Discord caps a message at 2000 characters, so
anything longer is split on line boundaries rather than truncated or dropped —
a screening report is exactly the kind of thing that runs long and is useless
cut in half.

Environment:
  DISCORD_POST_URL   the bot's /postmessage endpoint (required)
  DISCORD_CHANNEL_ID optional; the service falls back to its own default
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

LIMIT = 1900          # headroom for the code fence we may add
TIMEOUT = 25


def chunks(text: str, limit: int = LIMIT) -> list[str]:
    """Split on line boundaries, never mid-line, never mid-word."""
    out: list[str] = []
    buf: list[str] = []
    size = 0
    for line in text.splitlines():
        # A single line longer than the limit still has to go somewhere.
        while len(line) > limit:
            if buf:
                out.append("\n".join(buf))
                buf, size = [], 0
            out.append(line[:limit])
            line = line[limit:]
        if size + len(line) + 1 > limit and buf:
            out.append("\n".join(buf))
            buf, size = [], 0
        buf.append(line)
        size += len(line) + 1
    if buf:
        out.append("\n".join(buf))
    return [c for c in out if c.strip()]


def post(content: str, url: str, channel_id: str = "") -> bool:
    payload: dict = {"content": content}
    if channel_id:
        payload["channel_id"] = channel_id
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        print(f"discord post failed {exc.code}: {exc.read()[:300]!r}", file=sys.stderr)
    except (urllib.error.URLError, OSError) as exc:
        print(f"discord post failed: {exc}", file=sys.stderr)
    return False


def main() -> int:
    url = os.environ.get("DISCORD_POST_URL", "").strip()
    if not url:
        # Not configured is not a failure — the pipeline's work is already
        # committed, and failing the job here would obscure that.
        print("DISCORD_POST_URL not set; skipping notification", file=sys.stderr)
        return 0

    text = sys.stdin.read().strip()
    if not text:
        return 0

    fence = "--code" in sys.argv
    channel = os.environ.get("DISCORD_CHANNEL_ID", "").strip()

    ok = True
    parts = chunks(text)
    for i, part in enumerate(parts):
        body = f"```\n{part}\n```" if fence else part
        if len(parts) > 1:
            body = f"{body}\n_({i + 1}/{len(parts)})_"
        ok = post(body, url, channel) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
