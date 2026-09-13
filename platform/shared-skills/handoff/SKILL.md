---
name: handoff
description: Compact conversation state into structured handoff documents.
---

# Handoff

Synthesize and compact current task context, progress, and pending decisions into a structured handoff document for a subsequent agent session.

## Guidelines

1. **Storage location:** Save handoff documents to the operating system temporary directory (e.g. `/tmp/handoff-<timestamp>.md`), never inside the working repository.
2. **Reference existing artifacts:** Cite file paths, specs, ADRs, PRs, and commit hashes instead of duplicating full contents.
3. **Redact secrets:** Ensure all tokens, passwords, and sensitive API keys are stripped (`<REDACTED>`).
4. **Suggested skills:** Explicitly recommend skills for the next agent to invoke based on task state.

## Document Structure

```markdown
# Session Handoff: [Task Name]

## 1. Goal & Context
Brief summary of the overarching objective and user requirements.

## 2. Work Completed
- Key modifications, files changed, and features implemented.
- Tests executed and pass/fail status.

## 3. Current State & Known Issues
- What is currently working.
- Any failing tests, unexpected behaviors, or open blockers.

## 4. Next Immediate Actions
Ordered list of actionable steps for the next agent to execute.

## 5. Suggested Skills
Recommended skills (e.g., `tdd`, `diagnosing-bugs`, `code-review`, `to-spec`).
```
