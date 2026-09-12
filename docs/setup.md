# Set up Aidee

This guide is written for both people and chatbots. A chatbot must interview the owner before recommending commands. A terminal-enabled agent may run read-only checks, but it must show the final plan and receive approval before changing the server.

## Two-stage conversation

A new owner cannot begin inside their Aidee controller's Telegram chat because the controller and bot do not exist yet.

1. The owner gives the README prompt to an existing independent chatbot.
2. That chatbot interviews the owner and guides host and controller installation.
3. After the controller bot is connected, the chatbot prepares a non-secret setup summary.
4. The owner sends that summary to the controller in Telegram.
5. The controller confirms the summary, writes structured configuration, and curates durable memory.

Chat history is useful evidence, but it is not the configuration source of truth. Do not copy secrets or the raw transcript into memory.

## Safety rules

1. Never request or receive passwords, API keys, bot tokens, SSH private keys, recovery codes, or access tokens in chat.
2. Enter secrets through masked terminal input or an authenticated dashboard reached through an SSH tunnel.
3. Never pipe a remote script directly into a shell. Clone a pinned Aidee release, inspect it, then run its local scripts.
4. Do not expose the Hermes API or dashboard directly to the public internet.
5. Do not add project or client credentials until host access and secret entry have passed validation.
6. Stop before destructive, paid, DNS, firewall, or account-level actions and ask for approval.

## Interview

Ask one section at a time. Explain unfamiliar terms in plain language.

### 1. Owner and experience

- What name should the assistants use for their owner?
- How comfortable is the owner with terminals, SSH, DNS, Docker, and Git?
- Can the chatbot run terminal commands, or will it guide the owner?

### 2. Server

- Does the owner already have a VPS?
- If yes, which provider, operating system, architecture, CPU, memory, and storage does it have?
- If no, what region, monthly budget, and provider preference do they have?
- Does the owner already have SSH key access?

The first pilot supports a dedicated x86-64 VPS running Ubuntu 24.04 or 26.04. Use at least 2 vCPU, 8 GB RAM, and 60 GB storage for a small pilot. Recommend 4 vCPU, 16 GB RAM, and 100 GB storage when coding agents or several assistants will run concurrently.

### 3. Access

- Does the owner have a domain?
- Do they want dashboards available remotely?
- Can they install Tailscale on their phone?
- If they do not want Tailscale, can they use an SSH tunnel?
- Does the provider firewall currently expose SSH to the whole internet?

A domain is optional. Keep the dashboard bound to server loopback. Use Tailscale for routine private phone access or an SSH tunnel for temporary desktop access. Cloudflare Tunnel and Access may be added later.

### 4. Fleet

- How many assistants are needed for the pilot?
- What is each assistant's name, purpose, and project scope?
- Which assistants need stronger container, credential, or network isolation?
- What CPU, memory, and storage limits should each receive?

Start with one assistant. Validate it before creating the rest.

### 5. Models and interfaces

- Which model provider will Hermes use?
- Which messaging channel should each assistant use?
- Which MCP servers should each assistant receive?
- Which coding agent should handle implementation work?
- Which actions require human approval?

Start with one messaging channel, one narrowly scoped MCP server, and one coding adapter. Use MCP tool allowlists for systems that can write, purchase, publish, delete, or contact people.

### 6. Recovery

- Should Git-safe configuration and selected Markdown memory be backed up to a private Git repository?
- If yes, will the owner use GitHub, GitLab, or another Git host?
- Where should encrypted non-Git backups be stored?
- How long should session history be retained?

Git backup is optional. Credentials, databases, logs, and tokens never enter Git, even when the repository is private.

## Required plan

Before changing anything, summarize:

- Supported server and resource checks.
- SSH and firewall changes.
- Aidee version and Hermes image version.
- Controller privilege boundary.
- Each planned assistant and its limits.
- Dashboard access method.
- Messaging, MCP, coding, and observability integrations.
- Git and encrypted backup choices.
- Expected external costs.
- Manual steps and approval points.
- Validation and rollback steps.

Ask the owner to approve this plan.

## Installation sequence

After approval:

1. Connect over SSH instead of a provider's browser console.
2. Install Git if the clean host does not provide it.
3. Clone the Aidee repository and check out the selected release.
4. Run `./platform/scripts/preflight-host.sh`.
5. Review `platform/scripts/bootstrap-host.sh`.
6. Run `sudo ./platform/scripts/bootstrap-host.sh`.
7. Reboot and reconnect through the protected SSH path.
8. Install the selected Aidee revision under `/opt/aidee/source`.
9. Run `platform/scripts/verify-host.sh`.
10. Initialize private fleet state with `platform/scripts/init-fleet.sh`.
11. Install the pinned unprivileged controller runtime with `platform/scripts/install-controller.sh`.
12. Install its loopback-bound dashboard service.
13. Install and authenticate Tailscale when the owner selected phone access.
14. Publish the dashboard privately with Tailscale Serve.
15. Enter model and messaging credentials outside chat.
16. Start and validate the controller gateway.
17. Transfer the approved non-secret setup summary to the controller.
18. Provision and validate one assistant.
19. Provision remaining assistants one at a time.
20. Configure optional private Git and encrypted backups.
21. Run the recovery test in [recovery.md](recovery.md).

The project status identifies which steps are implemented. Do not invent commands for unfinished steps.

## Completion report

Report:

- What changed.
- Which checks passed or failed.
- Which ports are listening and where they are bound.
- Which assistants are healthy.
- Whether any secret entered chat, shell history, logs, or Git.
- How to stop the fleet.
- How to recover it.
- Remaining manual work.
