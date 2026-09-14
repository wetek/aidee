---
name: controller-update
description: Checks Aidee releases and runs the fleet updater after Telegram approval. Use when the owner asks to check or update Aidee, or when the daily update check finds a newer tag.
---

# Controller update

Read `docs/update-controller.md` from the latest fetched Aidee release.

Keep each response under 120 words unless preview or apply output needs more.

## Notice

When a newer tag exists, compose one Telegram notice. Do not run sudo on
that first message. Do not apply from an unanswered cron run.

Shape:

~~~text
✨ Aidee <tag> is ready

You're on <installed>.

What's new
• <at most 3 short owner-facing bullets from the release notes>

Preview first. Apply updates the host, controller, image, and assistants
and can take several minutes.
~~~

Never write Options or numbered choices in the notice body.

On a cron run, Telegram clarify is unavailable. Pipe the notice to
`/opt/aidee/source/platform/controller-tools/send-telegram-choices.py`
with `--choice "Start update"` and `--choice "Not now"`, then respond
with `[SILENT]`.

In an interactive Telegram chat, send that same notice with the
interactive clarify tool. The only labels are Start update and Not now.

Do not put SSH commands in the notice.

## After Start update

Run:

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh --release TAG --preview
~~~

Summarize the planned actions in short bullets. Then send one Telegram
clarify whose only labels are Apply now and Cancel. Do not write those
labels in the message body.

Tell the owner that apply can take several minutes.

## After Apply now

Run:

~~~bash
sudo /opt/aidee/source/platform/scripts/update-host.sh --release TAG --apply --approved
~~~

Wait until it finishes. Do not start a second apply. `--approved` is valid
only after the owner chose Apply now in this chat.

Report host, controller, cron, image, and assistant results. Name any
rollback or incomplete onboarding step.

## Fallback

If Telegram buttons are unavailable, give the SSH preview and apply commands
from `docs/update-controller.md` and wait.
