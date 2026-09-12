# Contributing to Aidee

Aidee is in a private pilot phase. Small changes that improve a tested installation path are preferred over broad abstractions.

## Before opening a change

1. Read `docs/system-design.md` and the accepted architecture decisions.
2. Keep public code separate from owner identity, infrastructure, memory, and credentials.
3. Do not weaken controller, container, dashboard, or secret boundaries for convenience.
4. Update setup and recovery documentation when behavior changes.

## Validate locally

Create a Python environment, install `requirements-dev.txt`, then run:

~~~bash
bash -n platform/scripts/*.sh
shellcheck platform/scripts/*.sh
python tests/validate_repository.py
~~~

The clean-VPS pilot remains the final test for installation changes.

## Security reports

Follow `SECURITY.md`. Do not report vulnerabilities or leaked credentials in public issues.
