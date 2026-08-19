#!/usr/bin/env bash
# The jobloop worker. One script, called by both timers.
#
# Runs on this machine against the existing Claude Code subscription rather
# than the cloud, which cannot reach a PRIVATE repo without the GitHub App
# connection — gated behind Team/Enterprise settings this account can't
# configure. Same work, no extra billing; the machine just has to be awake.
#
# THE GATE, and it is the whole point of this file: an idle repo must cost
# nothing. `jt work` answers "is there anything to do" deterministically and
# for free, and Claude is not started unless the answer is yes. Work means a
# queued Discord request or an untailored JD — nothing else. There is no
# heartbeat, no "check in case", no hourly sweep: a run happens because
# Aditya asked for something.
#
#   ./run-routine.sh          gate, then work
#   ./run-routine.sh --force  run regardless (debugging)
set -uo pipefail

ROOT="${JOBLOOP_ROOT:-/home/aditya/Work/repos/jobloop}"
cd "$ROOT" || exit 1

export DISCORD_POST_URL="${DISCORD_POST_URL:-https://discordbot-f6q5ge4umq-uc.a.run.app/postmessage}"
export DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-1539333966384074923}"
export PATH="$HOME/.local/bin:$PATH"

LOG="$ROOT/.routine.log"
FORCE="${1:-}"

# One worker at a time. Two `claude -p` runs in this repo would race on the
# working tree and on the push. Non-blocking: if a run is already going it is
# already doing this work, and queueing waiters just stacks up no-ops.
exec 9>"$ROOT/.jobloop.lock"
flock -n 9 || exit 0

# Requests arrive by git — Actions writes them, this machine pulls them.
git pull --rebase --autostash --quiet origin main 2>>"$LOG" \
    || echo "$(date -Is) pull failed, continuing on local state" >> "$LOG"

# --- the gate -------------------------------------------------------------
# Everything above this line is free. Nothing below it is.
if [ "$FORCE" != "--force" ]; then
    [ -d .venv ] || uv venv >/dev/null 2>&1
    if ! .venv/bin/jt work -q >/dev/null 2>&1; then
        exit 0                      # idle. No model, no tokens, no log noise.
    fi
fi

echo "=== $(date -Is) ===" >> "$LOG"
.venv/bin/jt work >> "$LOG" 2>&1
uv pip install -q -e . >/dev/null 2>&1

# Tools are allowlisted rather than skipping permission checks outright: this
# runs unattended, so the blast radius should be what the routine needs and
# nothing else. Gmail is read-only and only used when a `mail` request is
# queued.
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
