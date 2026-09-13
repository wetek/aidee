# ADR 0006: Verified controller onboarding

Status: accepted

## Decision

Use Tailscale Serve as the default automated phone-access adapter. Offer a temporary SSH tunnel and show Cloudflare as a planned custom-domain option.

After owner authorization, make Telegram branding the controller's first task. The controller drafts its profile and avatar, requests approval, applies changes through the Telegram Bot API, and reads them back.

Add the verified private dashboard URL as the Telegram menu button when selected.

Do not report controller setup as complete until:

- The owner is paired or allowlisted.
- Telegram profile changes pass read-back verification.
- The owner confirms that the dashboard opens from their phone.

## Reason

The first pilot reported completion while remote dashboard access and the planned bot profile were unfinished. It also generated a handoff from stale chat history. Completion must come from verified server state.
