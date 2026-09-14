# Aidee

Aidee is a self-hosted system for running a private fleet of AI assistants.

Aidee uses [Hermes Agent](https://hermes-agent.nousresearch.com/) as its first supported runtime. Each assistant has its own identity, memory, configuration, credentials, tools, and resource limits. Assistants can use MCP servers and task-scoped coding agents.

> [!WARNING]
> Aidee is pre-alpha software undergoing its first VPS pilot. Do not use it with production or client credentials yet.

## Setup with a chatbot

Copy this prompt into a chatbot that can read public web pages:

~~~text
Help me install and configure Aidee on my own server.

Before replying, read and follow this setup guide:

https://raw.githubusercontent.com/wetek/aidee/main/docs/setup.md

The guide contains the complete interview, response format, safety rules, setup plan, and installation handoff. Apply its writing rules to every response. Do not assume that slash commands or agent skills are available.

If the guide cannot be loaded, stop and name it. Do not guess its contents, commands, paths, or current release.

Complete all six interview sections before asking me to run a command. Then show me the complete plan and wait for my approval. After approval, produce the guide's single bootstrap block. The Aidee setup program should handle the remaining host work. Never pipe downloaded code into a shell.

Start with `Aidee setup [1/6]` and ask only the first interview question. Account for my technical experience.

Never ask me to paste passwords, API keys, SSH private keys, or access tokens into this chat. Use masked terminal input or an Aidee dashboard reached through an SSH tunnel for secrets.

Keep a structured record of my non-secret answers. Once my Aidee controller is available in Telegram, help me transfer the approved setup summary so it can write the durable configuration and curated memory.
~~~

A terminal-enabled coding agent can inspect the cloned repository and read [docs/setup.md](docs/setup.md) directly.

## Update an existing controller

Copy this prompt into the installed Aidee controller:

~~~text
Check for the latest Aidee release and guide me through the fleet update.

Read and follow:
https://raw.githubusercontent.com/wetek/aidee/main/docs/update-controller.md

Give me the documented SSH preview command. Summarize what it will change and
wait for my approval before giving me the apply command. Do not run the
root-owned updater from this chat or from a cron.
~~~

Alpha 13 and later update the host, controller, and registered assistants
through one owner-approved command.

## Current scope

The first pilot targets one owner using a dedicated Ubuntu VPS. It will prove:

- One unprivileged controller and a narrow root-owned administration helper.
- Multiple isolated Hermes assistants.
- One shared assistant image with common coding and MCP runtimes.
- Telegram, MCP configuration, private Git state backup, and one coding-agent adapter.
- Recovery on a clean VPS.

Tailscale is the recommended first option for private phone access. Cloudflare and Langfuse are optional integrations. Other agent runtimes and multi-user teams are outside the first release.

## Repository layout

~~~text
setup.sh        Resumable host and controller setup program
docs/           Architecture, setup, recovery, and decisions
platform/       Versioned Aidee defaults, schemas, policies, and host tools
fleet-template/ Git-safe templates for private server state
~~~

The public repository contains no deployed fleet state or credentials. Setup creates private state under `/var/lib/aidee`. The owner may back up approved configuration and Markdown memory to a private GitHub or GitLab repository.

## Start here

Read [the setup guide](docs/setup.md) and [the current project status](docs/project-status.md).

## License

Aidee is licensed under the Apache License 2.0. Hermes Agent is a separate project with its own license and maintainers. Aidee is not affiliated with or endorsed by Nous Research.
