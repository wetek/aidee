# ADR 0006: Verified controller onboarding

Status: accepted

## Decision

Use Tailscale Serve as the default automated phone-access adapter. Offer a temporary SSH tunnel and show Cloudflare as a planned custom-domain option.

On every user message, including greetings, require the controller to run the
durable onboarding gate. A Hermes `pre_llm_call` plugin injects that offer when required steps are
still incomplete and the owner has not answered. The gate records one resume
decision. `Not now` records that the owner was prompted and suppresses repeat
offers until manual reopen or a later schema adds a required step. It does not
create a time-based reminder.

After resume, the owner may configure Telegram branding or explicitly keep the
current profile. When accepted, the controller drafts its profile and avatar,
requests approval, applies changes through the Telegram Bot API, and reads them
back.

Add the verified private dashboard URL as the Telegram menu button when selected.
That URL is the published origin for that bot: Tailscale by default, or a
custom HTTPS hostname when the owner recorded one. Write descriptions for the
default Telegram language and `en`. Do not put dashboard URLs in bio text.

Offer a daily Aidee update check. The scheduled task may fetch and preview a newer release, but it must ask the owner before knowledge sync and must never update root-owned files.

Do not report controller setup as complete until:

- The owner is paired or allowlisted.
- The Telegram profile choice is completed or explicitly skipped.
- The owner confirms that the dashboard opens from their phone.
- The selected update-check state is active or disabled.

Every applicable optional step must also be completed or explicitly skipped
before the full onboarding rollup becomes complete. Legacy `deferred` state
migrates to pending.

## Reason

The first pilot reported completion while remote dashboard access and the planned bot profile were unfinished. It also generated a handoff from stale chat history. Completion must come from verified server state.
