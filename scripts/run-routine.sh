#!/usr/bin/env bash
# Local jobloop routine.
#
# Runs on this machine against the existing Claude Code subscription instead of
# the cloud routine, which cannot reach a PRIVATE repo without the GitHub App
# connection — and that connection is gated behind Team/Enterprise settings
# this account can't configure. Same work, same prompt, no extra billing; the
# only cost is that the machine has to be awake.
set -uo pipefail

ROOT="${JOBLOOP_ROOT:-/home/aditya/Work/repos/jobloop}"
cd "$ROOT" || exit 1

export DISCORD_POST_URL="${DISCORD_POST_URL:-https://discordbot-f6q5ge4umq-uc.a.run.app/postmessage}"
export DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-1539333966384074923}"
export PATH="$HOME/.local/bin:$PATH"

# Keep the venv current before handing over.
[ -d .venv ] || uv venv >/dev/null 2>&1
uv pip install -q -e . >/dev/null 2>&1

LOG="$ROOT/.routine.log"

# Shared with scripts/drain-inbox.sh. Two `claude -p` runs in this repo would
# race on the working tree and on the push. The hourly run waits rather than
# skipping: its work is not optional.
exec 9>"$ROOT/.jobloop.lock"
flock 9

echo "=== $(date -Is) ===" >> "$LOG"

# Tools are allowlisted rather than skipping permission checks outright: this
# runs unattended, so the blast radius should be the things the routine
# actually needs and nothing else.
timeout 1800 claude -p "$(cat scripts/routine-prompt.md)" \
    --permission-mode acceptEdits \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep,mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Gmail__get_thread" \
    >> "$LOG" 2>&1
status=$?

if [ $status -ne 0 ]; then
    echo "routine exited $status" >> "$LOG"
    printf 'jobloop routine failed (exit %s). Check .routine.log on the workstation.' "$status" \
        | python3 scripts/discord_post.py 2>/dev/null || true
fi
exit $status
