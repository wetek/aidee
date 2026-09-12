# Aidee project status

Status: public baseline and first VPS pilot in progress
Release: pre-alpha, unreleased

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
- Provider-neutral recovery and migration contracts.
- Chatbot-guided setup interview.

## Not implemented

- Root-owned narrow administration helper.
- Hermes image pinning and assistant container lifecycle.
- Assistant provisioning commands.
- Telegram, MCP, private Git, and coding-agent validation.
- Encrypted non-Git backup and restore.
- End-to-end tests on a clean VPS.

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

Complete the public baseline, publish it, then run the host preflight on the pilot VPS. Keep provider identifiers and live host details in a private operator record.
