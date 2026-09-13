# Set up Aidee

This is the complete instruction file for people and chatbots. Do not require another file before starting the interview.

Before the first response:

1. Start with `Aidee setup [1/6]`.
2. Ask one question.
3. Give numbered options when likely answers are known.
4. Put the recommended option first and explain it in one sentence.
5. Wait for the answer.

Apply these writing rules to every response:

- Use short sentences and plain words.
- Remove filler, praise, decorative symbols, and generic conclusions.
- Do not use tables on a phone-sized screen.
- Do not repeat the full setup record after each answer.
- State facts, decisions, and the next action.
- Default to 120 words or fewer.
- Expand only for safety, a required decision, or an error.

The full [wizard format](wizard-style.md) and [unslop skill](../platform/shared-skills/unslop/SKILL.md) are maintainer references. This guide includes the rules required for setup.

## Setup states

Follow these states in order:

1. `interview`: Ask all questions in sections 1 through 6. Do not ask the owner to run commands.
2. `plan`: Show the complete plan, costs, manual actions, risks, and validation steps.
3. `approval`: Wait for the owner to reply `approve`.
4. `install`: Give the single bootstrap block in this guide. The setup program handles later host commands.
5. `validate`: Run the documented checks without changing the approved scope.
6. `handoff`: Record confirmed configuration and report unfinished work.

Never enter `install` before completing all six interview sections and receiving approval. Read-only terminal commands are still commands and belong after approval.

## Two-stage conversation

A new owner cannot begin inside their Aidee controller's Telegram chat because the controller and bot do not exist yet.

1. The owner gives the README prompt to an existing independent chatbot.
2. That chatbot interviews the owner and guides host and controller installation.
3. After the controller bot is connected, the chatbot prepares a non-secret setup summary.
4. The owner sends that summary to the controller in Telegram.
5. The controller confirms the summary, writes structured configuration, and curates durable memory.

Chat history is useful evidence, but it is not the configuration source of truth. Do not copy secrets or the raw transcript into memory.

## Setup record

Store confirmed information by purpose:

- Stable owner preferences and working style belong in `USER.md`.
- Assistant identity and purpose belong in `SOUL.md`.
- Server, assistant, integration, resource, and approval choices belong in structured fleet configuration.
- Temporary command output and diagnostic logs are not durable memory.
- Credentials and authorization links never belong in chat, memory, or Git.

At handoff, send the controller a concise non-secret summary. Do not send the full setup transcript.

## Safety rules

1. Never request or receive passwords, API keys, bot tokens, SSH private keys, recovery codes, or access tokens in chat.
2. Enter secrets through masked terminal input or an authenticated dashboard reached through an SSH tunnel.
3. Never pipe a remote script directly into a shell. Clone a pinned Aidee release, inspect it, then run its local scripts.
4. Do not expose the Hermes API or dashboard directly to the public internet.
5. Do not add project or client credentials until host access and secret entry have passed validation.
6. Stop before destructive, paid, DNS, firewall, or account-level actions and ask for approval.

## Interview

Ask one question at a time. Follow `wizard-style.md`. Explain unfamiliar terms in plain language.

### 1. Owner and experience

- What name should the assistants use for their owner?
- How comfortable is the owner with terminals, SSH, DNS, Docker, and Git?

Do not ask the owner to choose who runs each command. If the chatbot has no terminal tools, record `guided` mode. After plan approval, the owner pastes one bootstrap block and the local setup program takes over.

### 2. Server

- Does the owner already have a VPS?
- If yes, which provider, operating system, architecture, CPU, memory, and storage does it have?
- If no, what region, monthly budget, and provider preference do they have?
- Does the owner already have SSH key access?

The first pilot supports a dedicated x86-64 VPS running Ubuntu 24.04 or 26.04. Use at least 2 vCPU, 8 GB RAM, and 60 GB storage for a small pilot. Recommend 4 vCPU, 16 GB RAM, and 100 GB storage when coding agents or several assistants will run concurrently.

Missing swap is a warning, not a setup blocker. Do not create swap automatically. For a host with about 8 GB RAM that will run coding workloads, include optional swap in the plan and explain the disk and performance tradeoff.

### 3. Access

- Which dashboard access method do they want?
  1. Tailscale private HTTPS address (recommended and automated).
  2. Cloudflare custom subdomain (planned, not automated in Alpha 5).
  3. Temporary SSH tunnel.
  4. Another method.
- Do they want the verified dashboard URL as the Telegram bot menu button?
- Does the provider firewall currently expose SSH to the whole internet?

A domain is optional. Keep the dashboard bound to server loopback. Use Tailscale for routine private phone access or an SSH tunnel for temporary desktop access. If the owner selects Cloudflare, stop before generating the Alpha 5 plan and explain that its adapter is not implemented yet.

After the server is on the tailnet, the controller gives the owner the phone steps: install the Tailscale app, sign in with the same email used to approve the server, turn the VPN on, then open the dashboard from the Telegram bot menu. See `platform/docs/tailscale.md`.

### 4. Fleet

- How many assistants are needed for the pilot?
- What is each assistant's name, purpose, and project scope?
- Which assistants need stronger container, credential, or network isolation?
- What CPU, memory, and storage limits should each receive?

Start with one assistant. Validate it before creating the rest.

### 5. Models and interfaces

- Which model provider will Hermes use?
- Which messaging channel should each assistant use?
- For Telegram, should the owner use DM pairing or a numeric allowlist?
- Which MCP servers should each assistant receive?
- Which coding agent should handle implementation work?
- Which actions require human approval?

Start with one messaging channel, one narrowly scoped MCP server, and one coding adapter. Use MCP tool allowlists for systems that can write, purchase, publish, delete, or contact people.

Recommend Telegram DM pairing for the first owner. The owner messages their bot, receives a one-time code, and approves it through the protected dashboard. This avoids using an unrelated Telegram bot to discover a numeric user ID. Never enable `*` access.

BotFather creates the bot and its username. After owner authorization, the controller can update its display name, descriptions, commands, menu button, and JPG avatar through the Telegram Bot API.

The controller checks for an image-generation tool during first-run onboarding. If one is available, it asks for a style and generates options. Otherwise, it requests a JPG upload. It always shows the complete profile and waits for approval before changing Telegram.

### 6. Recovery

- Should Git-safe configuration and selected Markdown memory be backed up to a private Git repository?
- If yes, will the owner use GitHub, GitLab, or another Git host?
- Where should encrypted non-Git backups be stored?
- How long should session history be retained?
- Should the controller check once a day for Aidee updates and ask before syncing?

Git backup is optional. Credentials, databases, logs, and tokens never enter Git, even when the repository is private.

Recommend the daily update check. It performs preview-only discovery and stays silent when nothing changed. It never applies an update from cron.

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

## Setup plan file

Convert the approved answers into JSON that matches `platform/schemas/setup-plan.schema.json`. Show the JSON in the plan review.

The plan may contain names, preferences, provider choices, repository URLs, and approval rules. It must not contain passwords, private keys, API keys, bot tokens, authorization URLs, or recovery codes.

Use this shape:

~~~json
{
  "schema_version": 1,
  "release": "v0.1.0-alpha.5",
  "owner": {
    "name": "Example Owner",
    "experience": "guided"
  },
  "server": {
    "provider": "google_cloud",
    "dashboard_access": "tailscale"
  },
  "controller": {
    "model_provider": "gemini",
    "messaging": ["telegram"],
    "telegram": {
      "access": "pairing",
      "branding": "offer",
      "avatar": "generate_or_upload",
      "menu_button": true
    }
  },
  "fleet": {
    "assistants": [
      {
        "name": "Example Assistant",
        "kind": "coding",
        "purpose": "Maintain one approved project.",
        "coding_agent": "opencode",
        "repository": "https://github.com/example/project",
        "authority": "pull_request"
      }
    ]
  },
  "recovery": {
    "private_git": "later",
    "provider": null
  },
  "updates": {
    "daily_check": true
  }
}
~~~

Alpha 5 accepts:

- Experience: `beginner`, `guided`, or `advanced`.
- Dashboard access: `tailscale` or `ssh_tunnel`.
- Messaging: `telegram`, `discord`, or `slack`.
- Telegram access: `pairing` or `allowlist`.
- Telegram branding: `offer`.
- Telegram avatar: `generate_or_upload`.
- Assistant kind: `personal`, `coding`, `client`, or `project`.
- Coding agent: `opencode`, `claude_code`, `codex`, or `none`.
- Authority: `investigate_only`, `pull_request`, or `approved_merge_deploy`.
- Private Git: `later` or `disabled`.
- Daily update check: `true` or `false`.

Cloudflare and immediate private Git setup remain planned options. Do not place them in an Alpha 5 setup plan.

Alpha 5 delivers update notices through Telegram. Set `daily_check` to `false` when Telegram is not selected.

## Bootstrap handoff

After the owner replies `approve`, replace `SETUP_PLAN_JSON` below with the approved JSON. Give the owner this single block without changing its other lines:

~~~bash
sudo apt-get update
sudo apt-get install -y git
git clone --branch v0.1.0-alpha.5 --depth 1 https://github.com/wetek/aidee.git
cd aidee
cat > setup-plan.json <<'AIDEE_PLAN'
SETUP_PLAN_JSON
AIDEE_PLAN
python3 platform/setup/plan.py setup-plan.json
sudo ./setup.sh --plan setup-plan.json
~~~

The owner pastes the whole block into an SSH terminal. Do not ask them to paste successful output into chat.

## Setup program

`setup.sh` handles:

1. Plan validation and host preflight.
2. Host packages, Docker, and controller account.
3. Reboot progress.
4. Pinned Aidee and Hermes installation.
5. Private fleet state.
6. Loopback dashboard.
7. Tailscale installation and private dashboard access when selected.
8. Root-owned narrow administration helper.
9. Shared assistant image build and validation.
10. Controller model and messaging readiness.
11. Gateway startup and owner authorization.
12. Telegram bot branding offer.
13. Telegram dashboard menu button.
14. Phone dashboard verification.
15. Optional daily update check that always asks before syncing.
16. Non-secret Telegram handoff.

The program stores progress under `/var/lib/aidee/setup`. It prints one next action when it pauses.

After a reboot or manual authorization step, the owner reconnects, returns to the cloned `aidee` directory, and runs:

~~~bash
sudo ./setup.sh
~~~

The owner still creates or approves third-party accounts and credentials. The program must guide, wait, verify, and continue without receiving those secrets in chat.

The controller's first authorized conversation must offer Telegram branding. The owner may configure it now, defer it, or keep the current profile. If they continue, the controller generates an avatar when an image tool is available or requests a JPG upload, waits for approval, and applies the profile.

After controller onboarding passes, the owner can ask the controller to create an assistant. The controller uses one-question-at-a-time planning, waits for approval, and calls the narrow administration helper. Every assistant uses the validated shared image and separate state.

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
