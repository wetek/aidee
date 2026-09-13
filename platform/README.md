# Aidee platform

Shared, versioned runtime and behavior for Aidee.

This directory owns:

- The base container image.
- Shared instructions, skills, workflows, and defaults.
- Provisioning and controller tools.
- Schemas consumed by the Aidee controller and setup tools.
- Platform releases and rollback documentation.

Assistant identity, memory, and project-specific configuration are generated from `fleet-template` into private server state. They do not belong in this public repository.

## Current phase

Version 0.1.0 defines the contracts, host bootstrap, and setup flow. It does not yet install the controller or provision an assistant. See `docs/project-status.md`.

## Layout

~~~text
defaults/             Default values used by provisioning
docs/                 Platform-specific setup and versioning
policies/             State tracking and security rules
schemas/              Machine-readable configuration contracts
shared-instructions/  Rules that apply across the fleet
shared-skills/        Common Hermes skills
shared-workflows/     Common operational workflows
controller-tools/     Host administration interfaces
admin/                Root-owned narrow administration helper
container/            Shared assistant image
provisioning/         Assistant setup wizard
releases/             Release notes and manifests
scripts/              Repeatable host bootstrap and verification
~~~
