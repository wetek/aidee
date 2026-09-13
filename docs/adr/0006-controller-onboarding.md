# ADR 0006: Verified controller onboarding

Status: accepted

## Decision

Use Tailscale Serve as the default automated phone-access adapter. Offer a temporary SSH tunnel and show Cloudflare as a planned custom-domain option.

After owner authorization, require the controller to offer Telegram branding in its first conversation. The owner may proceed, defer it, or keep the current profile. When accepted, the controller drafts its profile and avatar, requests approval, applies changes through the Telegram Bot API, and reads them back.

Add the verified private dashboard URL as the Telegram menu button when selected.

Offer a daily Aidee update check. The scheduled task may fetch and preview a newer release, but it must ask the owner before knowledge sync and must never update root-owned files.

Do not report controller setup as complete until:

- The owner is paired or allowlisted.
- The Telegram profile choice is applied, deferred, or skipped.
- The owner confirms that the dashboard opens from their phone.
- The selected update-check state is active or disabled.

## Reason

The first pilot reported completion while remote dashboard access and the planned bot profile were unfinished. It also generated a handoff from stale chat history. Completion must come from verified server state.
