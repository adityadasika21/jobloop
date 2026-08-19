# Handling inbox requests

Read this ONLY when `jt inbox list` is non-empty. It is kept out of
`routine-prompt.md` on purpose: the hourly routine reads that prompt every
run, and most runs have an empty inbox — there is no reason to pay for
these instructions when there is nothing to apply them to.

`.venv/bin/jt inbox list --json` is work Aditya asked for from Discord and is
waiting on. He is more likely to be watching for these than for anything else
in this run, so they come before tailoring. If it is empty, skip the section.

Each request carries `id`, `kind`, `channel_id`, and the fields for its kind.
Reply in the channel it came from:

    DISCORD_CHANNEL_ID=<channel_id> python3 scripts/discord_post.py

and then `.venv/bin/jt inbox done <id>`. Mark it done even if the answer was
"I need more from you" — an unanswerable request that stays queued gets
answered again every hour.

### kind: freetext — from `/j`

`text` is what he typed, in his own words. Work out what he means and do it.
He will not name a job by slug, pick a status from a menu, or split one
thought into three commands, so assume one message carries several things.

Resolve the job with `.venv/bin/jt find "<his words>"`, which ranks every job
against the text. Take the top hit when it is clearly ahead; if two are close,
ask him which rather than guessing — an interview written onto the wrong
company's timeline corrupts both.

What he is probably doing, and what to run:

- **An interview happened** ("round 1 done", "they asked me about X", "went
  badly") → `jt debrief <slug>` for the template, fill it in, pipe it back
  with `jt debrief <slug> --apply -`. Put what they actually asked in
  `questions_asked`. Open a weakness **only** if he says something went badly,
  with HIS words in `quote`, never yours. "Answered fine" is not a weakness.
  Outcome is `pending` until he says otherwise. If he did not say when it was
  held, leave `held_at` empty rather than guessing a date.
- **A status moved** ("applied", "they rejected me", "got an offer") →
  `jt advance <slug> <status>`.
- **He built or shipped something** → treat it as `kind: context` below.
- **He wants a message** → `jt message <slug> --type <type> --scaffold`, then
  the pitch rules below.
- **He pasted a job posting** → `jt intake`, then tailor it in section 2.
- **He asked a question** → answer from `jt status`, `jt show`, `jt sql`.

THE RULE, unchanged: never record a number, a technology, a quote or an
outcome he did not say. If the message is too vague to act on, do nothing and
ask the one question that would unblock it. Doing nothing and saying why is a
good outcome; guessing is not.

### kind: context — from `/ctx`

`profile/pending-evidence.yaml` is already scaffolded and `text` is what he
typed. Fill in `units` per its `_instructions`, then
`.venv/bin/jt evidence add profile/pending-evidence.yaml`.

This writes to `master.yaml`, which every future resume and message is
generated from and which `jt verify` trusts absolutely. Claim only what he
said. `probe` is required and must be a question: if he could not answer it
from what he actually told you, the claim is too strong — weaken the claim,
never soften the probe. If the text is too vague to support an honest claim,
add nothing and say what you would need.

Reply with what `scripts/report_new_evidence.py` prints: the claim written,
and the probe it now commits him to answering.

### kind: message — from `/msg` and `/ln_msg`

`slug` and `type` are set and the scaffold already exists. Write only the
`pitch` paragraph, following the scaffold's `_instructions` for that type.
Then `.venv/bin/jt verify <slug> --message <type>` — it must pass — and
`.venv/bin/jt message <slug> --type <type>`. Post the rendered message.

A message that oversells is worse than no message: it gets the call, and the
call is where the overselling is discovered.


### kind: mail — from `/j check my mail`

Read-only. **Never send, reply, label, trash, or mark spam.**

Search the companies in `.venv/bin/jt status` that still have a live process —
not all of them, and not the whole inbox — plus a 3-day sweep for
application / interview / rejection mail. Build a JSON array of
`{thread_id, from, subject, date, snippet}` and pipe it to:

    .venv/bin/jt mail ingest - --auto-intake

Then `.venv/bin/jt mail needs-reply`, and report what moved. If nothing moved,
say so in one line — that is the common case and it should read as cheap.

This used to run every hour whether or not anything had happened. It is a
request now because it was the reason an idle repo cost anything at all.
