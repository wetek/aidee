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
bash -n setup.sh platform/scripts/*.sh
shellcheck setup.sh platform/scripts/*.sh
bash platform/scripts/build-dashboard-plugins.sh
python tests/validate_repository.py
python -m unittest discover -s tests -p 'test_*.py'
~~~

The clean-VPS pilot remains the final test for installation changes.

## Security reports

Follow `SECURITY.md`. Do not report vulnerabilities or leaked credentials in public issues.

Installed controllers may offer to draft optional product feedback as a public GitHub issue. That channel is for bugs, features, docs gaps, and insights. It is not a security channel.
