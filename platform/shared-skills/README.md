# Shared skills

Reusable Hermes skills that every assistant may receive.

`unslop/SKILL.md` applies to the public setup interview and generated assistant responses. Ordinary chatbots can read it as instructions even when they do not support installable skills.

`controller-onboarding/SKILL.md` runs in the controller's first authorized conversation. It verifies owner access, records the owner's Telegram branding choice, and confirms phone dashboard access.

`controller-update/SKILL.md` previews and applies owner-approved Aidee knowledge updates without root access.

`controller-feedback/SKILL.md` offers to draft a public GitHub issue when the owner hits a bug, feature request, docs gap, or insight. The owner reviews and submits it. Nothing is shared unless they ask.

`provision-assistant/SKILL.md` creates and validates isolated Aidee assistants through the narrow administration helper.

## Matt Pocock engineering workflows

Bundled engineering discipline skills installed for coding and project assistants:

- `tdd/SKILL.md`: Strict Red-Green-Refactor loop with minimal green steps and boundary testing.
- `diagnose/SKILL.md`: 6-step systematic debugging flow (Reproduce -> Minimise -> Hypothesise -> Instrument -> Fix -> Regression-test).
- `grill-me/SKILL.md`: Requirements interrogation, edge-case probing, and architectural clarity before coding.
- `to-prd/SKILL.md`: Converting conversations, ideas, and feature requests into actionable PRDs with acceptance criteria.
- `improve-architecture/SKILL.md`: Reducing complexity, modularity refactoring, and anti-entropy codebase cleanup.
