# Aidee project status

Status: first VPS pilot in progress
Release: `v0.1.0-alpha.9`

## Goal

Prove that an owner can use the Aidee setup guide to install a private fleet of Hermes assistants on a clean Ubuntu VPS.

## Implemented

- Public product boundary and fleet templates.
- Configuration schemas and state-tracking policy.
- Tested Ubuntu host preflight, bootstrap, and verification scripts.
- Pinned unprivileged Hermes controller installation.
- Loopback-bound controller dashboard service.
- Hardened persistent controller gateway service.
- Optional Tailscale installation and phone-access guide.
- Validated non-secret setup plans.
- Resumable host and controller setup through `setup.sh`.
- Mandatory controller first-conversation onboarding offer.
- Approved Telegram profile and avatar updates through the Bot API.
- Telegram owner and phone dashboard completion markers.
- Owner-selected Telegram profile status: applied, deferred, or skipped.
- Unprivileged controller knowledge preview and sync.
- Owner-approved daily update discovery through Hermes cron.
- Provider-neutral recovery and migration contracts.
- Chatbot-guided setup interview.
- Shared assistant image with pinned Hermes and OpenCode.
- Root-owned administration helper and controller-only Unix socket.
- Assistant create, start, stop, and status requests.
- Personal assistant provisioning through Telegram.
- Tailscale HTTPS ports for assistant dashboards.
- Fleet tab login management for assistant dashboards.

## Awaiting VPS validation

- Shared image reuse and cross-assistant isolation after a clean reinstall.
- Telegram, MCP, and coding-agent task checks on the pilot.
- Encrypted non-Git backup and restore.

## Not implemented

- End-to-end tests on a clean VPS.
- Cloudflare dashboard adapter.
- Assistant delete through the helper.

Do not describe Aidee as installable until the end-to-end pilot passes.

## Pilot sequence

1. Publish a sanitized pre-alpha repository.
2. Restrict SSH access on the pilot VPS.
3. Run host preflight and bootstrap from a pinned revision.
4. Verify Docker, directories, operating system, and the unprivileged controller account.
5. Implement and install the narrow administration helper.
6. Install the Hermes controller without root or Docker access.
7. Reach the controller dashboard through an SSH tunnel.
8. Configure credentials outside chat.
9. Provision one isolated assistant.
10. Validate Telegram, one MCP server, and one coding-agent task.
11. Provision a second assistant and verify file and credential isolation.
12. Configure optional private Git state backup.
13. Rebuild one assistant from Git-safe state and encrypted secrets.
14. Record failures and update Aidee before publishing an alpha release.

## Release gates

- A fresh Ubuntu host can complete the documented setup.
- The controller cannot run arbitrary root or Docker commands.
- Dashboards and APIs are not publicly exposed by default.
- No secret enters chat, Git, command history, or test logs.
- Two assistants remain isolated and survive a restart.
- Recovery succeeds using the recorded Aidee version, approved Git-safe state, and encrypted non-Git backup.
- Public-content and secret scans pass.

## Next action

Finish remaining pilot checks: Telegram, one MCP server, one coding-agent task, isolation after restart, and recovery. Keep provider identifiers and live host details in a private operator record.
