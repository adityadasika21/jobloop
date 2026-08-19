#!/usr/bin/env bash
# Drain inbox/ — the fast path.
#
# The hourly routine would answer these eventually, but "eventually" is up to
# an hour and /j is meant to feel like talking to something. This runs often,
# and costs nothing when there is nothing to do: it pulls, looks, and exits
# before starting Claude unless there is actually a request waiting.
#
# Serialised against the hourly routine with the same lock. Two `claude -p`
# runs in one repo would race on the working tree and on the push.
set -uo pipefail

ROOT="${JOBLOOP_ROOT:-/home/aditya/Work/repos/jobloop}"
cd "$ROOT" || exit 1

export DISCORD_POST_URL="${DISCORD_POST_URL:-https://discordbot-f6q5ge4umq-uc.a.run.app/postmessage}"
export DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-1539333966384074923}"
export PATH="$HOME/.local/bin:$PATH"

LOCK="$ROOT/.jobloop.lock"
LOG="$ROOT/.routine.log"

# Non-blocking: if the hourly routine holds the lock it is already handling
# the inbox, and piling up waiters would serialise a queue of no-ops.
exec 9>"$LOCK"
flock -n 9 || exit 0

# Actions pushes the request; this machine has to pull it.
git pull --rebase --autostash --quiet origin main 2>>"$LOG" || {
    echo "$(date -Is) drain: pull failed" >> "$LOG"; exit 0; }

shopt -s nullglob
pending=(inbox/*.yaml)
[ ${#pending[@]} -eq 0 ] && exit 0

echo "=== $(date -Is) drain: ${#pending[@]} request(s) ===" >> "$LOG"

[ -d .venv ] || uv venv >/dev/null 2>&1
uv pip install -q -e . >/dev/null 2>&1

timeout 900 claude -p "$(cat scripts/inbox-prompt.md)" \
    --permission-mode acceptEdits \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep" \
    >> "$LOG" 2>&1
status=$?

if [ $status -ne 0 ]; then
    echo "drain exited $status" >> "$LOG"
    printf 'jobloop inbox drain failed (exit %s). Check .routine.log on the workstation.' "$status" \
        | python3 scripts/discord_post.py 2>/dev/null || true
fi
exit $status
