# Aidee

Aidee is a self-hosted system for running a private fleet of AI assistants.

Aidee uses [Hermes Agent](https://hermes-agent.nousresearch.com/) as its first supported runtime. Each assistant has its own identity, memory, configuration, credentials, tools, and resource limits. Assistants can use MCP servers and task-scoped coding agents.

> [!WARNING]
> Aidee is pre-alpha software undergoing its first VPS pilot. Do not use it with production or client credentials yet.

## Setup with a chatbot

Copy this prompt into a chatbot that can read public web pages:

~~~text
Help me install and configure Aidee on my own server.

Read the Aidee setup guide at https://github.com/wetek/aidee/blob/main/docs/setup.md before giving me commands.
Interview me using that guide, account for my technical experience, and show me a complete plan before making changes.

Never ask me to paste passwords, API keys, SSH private keys, or access tokens into this chat. Use masked terminal input or an Aidee dashboard reached through an SSH tunnel for secrets.
~~~

A terminal-enabled coding agent can inspect the cloned repository and read [docs/setup.md](docs/setup.md) directly.

## Current scope

The first pilot targets one owner using a dedicated Ubuntu VPS. It will prove:

- One unprivileged controller and a narrow root-owned administration helper.
- Multiple isolated Hermes assistants.
- Telegram, MCP configuration, private Git state backup, and one coding-agent adapter.
- Recovery on a clean VPS.

Cloudflare and Langfuse are optional integrations. Other agent runtimes and multi-user teams are outside the first release.

## Repository layout

~~~text
docs/           Architecture, setup, recovery, and decisions
platform/       Versioned Aidee defaults, schemas, policies, and host tools
fleet-template/ Git-safe templates for private server state
~~~

The public repository contains no deployed fleet state or credentials. Setup creates private state under `/var/lib/aidee`. The owner may back up approved configuration and Markdown memory to a private GitHub or GitLab repository.

## Start here

Read [the setup guide](docs/setup.md) and [the current project status](docs/project-status.md).

## License

Aidee is licensed under the Apache License 2.0. Hermes Agent is a separate project with its own license and maintainers. Aidee is not affiliated with or endorsed by Nous Research.

