# Aidee glossary

**Aidee**

The public software and documentation used to install and operate a private fleet of AI assistants.

**Owner**

The single human who controls an Aidee installation and approves sensitive actions.

**Controller**

The unprivileged Hermes assistant that plans provisioning and maintenance, calls approved Aidee operations, and reports fleet health.

**Administration helper**

A root-owned program that exposes a small validated set of host and container operations. It does not accept arbitrary shell commands or controller-written Compose files.

**Assistant**

A persistent Hermes agent with its own identity, memory, configuration, credentials, tools, and project scope.

**Fleet**

The assistants and controller managed by one Aidee installation.

**Aidee platform**

The versioned defaults, schemas, policies, tools, and shared behavior used by the fleet.

**Fleet state**

The private controller registry and each assistant's identity, configuration, selected memory, and custom files.

**Runtime state**

Sessions, databases, logs, caches, packages, cloned repositories, and other files generated while an assistant runs.

**Git-safe state**

Fleet state approved for an optional private Git backup after a secret scan.

**Secret state**

Model keys, bot tokens, private keys, OAuth credentials, MCP tokens, and other values that never enter Git or chat.

**Project record**

The repositories, services, deployment references, decisions, and work tracker associated with a project.

**MCP server**

A tool provider connected to Hermes through the Model Context Protocol. Aidee limits exposed tools to the smallest useful set.

**Coding agent**

A task-scoped implementation tool that receives a bounded task, approved repository access, and validation requirements.

**Work item**

A durable record of a desired outcome, acceptance criteria, decisions, evidence, and status.

**Run**

One attempt by an assistant or coding agent to advance a work item.

**Capability grant**

Permission to perform named actions on specific resources.

**Decision request**

A question that requires the owner to change scope, authority, priorities, cost, or interpretation.

**Verified outcome**

A result supported by inspected artifacts and checks against stated acceptance criteria.
