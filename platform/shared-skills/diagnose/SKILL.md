---
name: diagnose
description: 6-step systematic debugging flow for resolving software bugs.
---

# Systematic Debugging (Diagnose)

Follow a 6-step root-cause debugging workflow. Never guess, assume, or shotgun debug by making random edits hoping tests pass.

## 6-Step Debugging Flow

```
1. REPRODUCE ---> 2. MINIMISE ---> 3. HYPOTHESISE
                                          |
6. REGRESSION <-- 5. FIX      <--- 4. INSTRUMENT
```

### Step 1: Reproduce

- Create a reliable, deterministic reproduction of the bug (a failing unit test, integration test, or minimal script).
- If the bug is intermittent or environment-dependent, isolate concurrency, timing, network, or environment state until it reproduces consistently.
- Verify the reproduction produces the exact failure reported.

### Step 2: Minimise

- Strip away extraneous context, large payloads, complex configs, and unrelated dependencies.
- Reduce the failing input or test case to the smallest possible example that still triggers the bug.
- Pinpoint the exact boundary or function where the bad state originates.

### Step 3: Hypothesise

- Form an explicit, falsifiable hypothesis about the underlying root cause.
- Read error tracebacks, inspect recent diffs, and check assumptions about state, types, and invariants.
- State clearly: "The bug occurs because condition X causes state Y at point Z."

### Step 4: Instrument

- Validate or refute the hypothesis by adding targeted logging, assertions, debugger breakpoints, or temporary inspections.
- Inspect the actual runtime state at each step of execution.
- If evidence refutes the hypothesis, return to Step 3 with new data. Do not write a fix until the root cause is proven.

### Step 5: Fix

- Write the minimal, targeted code change that directly corrects the verified root cause.
- Avoid broad workarounds, band-aid catches, or masking error symptoms.
- Ensure the fix adheres to surrounding architectural patterns and style.

### Step 6: Regression-test

- Run the reproduction test created in Step 1 and confirm it now passes.
- Run the full project test suite to verify that no existing functionality was broken.
- Retain the reproduction test in the permanent test suite to prevent regressions.

## Rules of Discipline

- **No shotgun debugging:** Never alter code without an active hypothesis and evidence.
- **Root cause over symptom:** Fix why bad state entered the system, not just where it crashed.
- **Evidence first:** Prove the cause before applying the fix.
