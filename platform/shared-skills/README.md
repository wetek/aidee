# Shared skills

Reusable Hermes skills that every assistant may receive.

`unslop/SKILL.md` applies to the public setup interview and generated assistant responses. Ordinary chatbots can read it as instructions even when they do not support installable skills.

`controller-onboarding/SKILL.md` runs at the start of every controller conversation until the onboarding gate returns silent or complete. It verifies owner access, records the owner's Telegram branding choice, and confirms phone dashboard access.

`controller-update/SKILL.md` notices a newer Aidee tag on Telegram, then previews and applies the fleet updater after the owner taps Start update and Apply now.

`controller-feedback/SKILL.md` offers to draft a public GitHub issue when the owner hits a bug, feature request, docs gap, or insight. The owner reviews and submits it. Nothing is shared unless they ask.

`provision-assistant/SKILL.md` creates and validates isolated Aidee assistants through the narrow administration helper.

`controller-dashboard-origin/SKILL.md` records the published HTTPS origin for one assistant dashboard when the owner chooses Tailscale or a custom hostname.

## Matt Pocock engineering workflows

Bundled engineering discipline skills installed for coding and project assistants:

- `code-review/SKILL.md`: Two-axis diff review (Standards compliance + Spec fidelity) via parallel sub-agents.
- `codebase-design/SKILL.md`: Deep modules, small interfaces, clean seams, and boundary testability.
- `diagnosing-bugs/SKILL.md`: 6-step root-cause diagnosis loop (Reproduce -> Minimise -> Hypothesise -> Instrument -> Fix -> Regression-test).
- `domain-modeling/SKILL.md`: Ubiquitous domain language, glossary in `CONTEXT.md`, and ADR recording.
- `grill-me/SKILL.md`: Relentless requirements interrogation and edge-case probing before coding.
- `grill-with-docs/SKILL.md`: Requirements interrogation paired with inline `CONTEXT.md` and ADR creation.
- `grilling/SKILL.md`: Core tree-structured interview protocol and decision frontier exploration.
- `handoff/SKILL.md`: State preservation, task snapshots, and context handoff between turns and sessions.
- `to-spec/SKILL.md`: Synthesizing conversations into structured technical specifications with acceptance criteria.
