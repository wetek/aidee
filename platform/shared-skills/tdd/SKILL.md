---
name: tdd
description: Strict Red-Green-Refactor loop for test-driven development.
---

# Test-Driven Development (TDD)

Enforce a strict Red-Green-Refactor cycle to ensure reliable, tested, and maintainable software.

## Core Cycle

Follow the three phases strictly in sequence. Never write production code without a failing test.

```
+------------+       +------------+       +------------+
|   1. RED   | ----> |  2. GREEN  | ----> | 3. REFACTOR|
| Write test |       | Make pass  |       | Clean up   |
+------------+       +------------+       +------------+
      ^                                         |
      +-----------------------------------------+
```

### Phase 1: RED (Write Failing Test)

1. Write a single, focused test that defines one expected behavior or requirement.
2. Run the test suite (`pytest`, `npm test`, `vitest`, `cargo test`, `go test`, etc.).
3. Verify the test **fails for the expected reason** (e.g. missing function, incorrect assertion), not because of syntax errors or bad test setup.

### Phase 2: GREEN (Make Test Pass)

1. Write the minimal production code necessary to make the failing test pass.
2. Do not write extra features, optimizations, or speculative code.
3. Run the test suite and verify that the new test passes along with all existing tests.

### Phase 3: REFACTOR (Improve Code Quality)

1. Clean up both implementation code and test code without changing behavior.
2. Eliminate duplication, improve naming, simplify control flow, and extract helpers.
3. Run the test suite after every refactoring edit to verify that tests remain green.

## Boundary and Edge-Case Testing

For every feature or bugfix, write tests covering:

- **Empty / Null values:** Empty strings, empty collections, `None`/`null`, missing fields.
- **Boundary values:** Off-by-one indices, min/max limits, zero, negative numbers.
- **Error paths:** Invalid inputs, network timeouts, file-not-found, permission errors.
- **Idempotency:** Calling an operation multiple times produces expected state.

## Verification Checklist

- [ ] A failing test was written and executed before modifying implementation code.
- [ ] Test failure mode was confirmed before writing the fix.
- [ ] Implementation was kept minimal to satisfy the test.
- [ ] Refactoring step was performed with all tests remaining green.
- [ ] Full test suite was executed via `terminal` and returned exit code 0.
