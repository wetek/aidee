---
name: diagnosing-bugs
description: 6-step root-cause diagnosis loop for hard bugs and regressions.
---

# Diagnosing Bugs

A disciplined 6-step root-cause analysis loop for resolving bugs and performance regressions without speculative edits.

## 6-Step Diagnosis Loop

```
1. REPRODUCE ---> 2. MINIMISE ---> 3. HYPOTHESISE
                                          |
6. REGRESSION <-- 5. FIX      <--- 4. INSTRUMENT
```

### Phase 1: Build a Feedback Loop (Reproduce)

Establish a tight, deterministic, agent-runnable verification command:

- Failing unit, integration, or end-to-end test.
- HTTP script or curl command against local services.
- Deterministic CLI command with fixture input.
- Captured event or trace replayed in isolation.

**Rules:**
- Redact secrets, tokens, and sensitive headers from outputs (`<REDACTED>`).
- Make the feedback loop fast (seconds, not minutes) and reliable.

### Phase 2: Minimise the Repro

- Shrink the failing input and reproduction scenario to the smallest possible case.
- Cut extraneous context, configuration, and unrelated steps until every remaining element is strictly load-bearing.

### Phase 3: Hypothesise

- Formulate 3–5 ranked, falsifiable hypotheses.
- Express each hypothesis in testable terms: *"If X is the cause, then changing Y will eliminate the bug."*

### Phase 4: Instrument

- Validate or refute hypotheses with targeted logging, assertions, or debugger breakpoints.
- Tag temporary debug logs (e.g. `[DEBUG-...]`) for clean removal later.
- For performance regressions, establish baseline metrics and profiler traces before changing code.

### Phase 5: Fix

- Write the minimal, targeted code change that directly fixes the verified root cause.
- Avoid masking symptoms or applying superficial workarounds.

### Phase 6: Regression Test & Cleanup

- Confirm the automated reproduction test now passes.
- Run the full test suite to guarantee zero regressions.
- Remove all temporary instrumentation and debug tags.
- Document the confirmed root cause and solution in the commit or pull request.
