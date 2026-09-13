# Shared skills

Reusable Hermes skills that every assistant may receive.

`unslop/SKILL.md` applies to the public setup interview and generated assistant responses. Ordinary chatbots can read it as instructions even when they do not support installable skills.

`controller-onboarding/SKILL.md` runs in the controller's first authorized conversation. It verifies owner access, records the owner's Telegram branding choice, and confirms phone dashboard access.

`controller-update/SKILL.md` previews and applies owner-approved Aidee knowledge updates without root access.

Initial skill targets:

- Investigate an incident before proposing implementation.
- Write a task brief with evidence and acceptance criteria.
- Delegate implementation to the configured coding agent.
- Validate tests, branch, pull request, and trace links.
- Report decisions and failures clearly.

Skills will be implemented and tested with the shared container image.

