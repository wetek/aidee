# Controller state template

Setup copies this directory into the private fleet state for the Aidee controller.

Planned additions during controller installation:

- Non-secret Hermes config.
- Optional dashboard route declarations.
- Host resource policy.
- Provisioning defaults selected for this VPS.
- Approved assistant operation requests under `requests/`.

The controller's `.env`, `auth.json`, databases, tokens, logs, and sessions remain outside Git.
