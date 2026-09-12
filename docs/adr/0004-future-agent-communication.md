# ADR 0004: Future agent communication

Status: accepted, deferred

## Decision

Add controller-to-assistant communication later through a private MCP service with narrow operations. Do not implement it in the initial platform.

## Reason

Hermes delegation handles child agents inside one instance. Separate persistent assistants need an authenticated boundary that does not expose files or credentials across projects.

