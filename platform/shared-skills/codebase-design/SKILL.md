---
name: codebase-design
description: Shared vocabulary and principles for designing deep modules.
---

# Codebase Design

Design **deep modules**: significant behavior behind a small interface, placed at a clean seam, testable through that interface.

## Glossary

- **Module**: anything with an interface and an implementation (function, class, package, or vertical slice).
- **Interface**: everything a caller must know to use the module correctly (types, invariants, ordering constraints, error modes, configuration).
- **Implementation**: internal body of code behind the interface.
- **Depth**: leverage at the interface. High behavior-to-interface ratio.
- **Seam**: a place where behavior can be altered without modifying code in that place (Michael Feathers).
- **Adapter**: a concrete implementation satisfying an interface at a seam.
- **Leverage**: caller benefit — more capability per unit of interface learned.
- **Locality**: maintainer benefit — changes and verification stay concentrated in one place.

## Deep vs Shallow Modules

- **Deep module**: small, clean interface concealing substantial internal logic and complexity.
- **Shallow module**: wide interface with minimal implementation (pass-throughs, excessive wrappers).

## Core Principles

1. **Depth is interface-level:** Internal composition can use private helper classes or subroutines without expanding the public interface.
2. **The deletion test:** If deleting a module causes complexity to vanish, it was a shallow pass-through; if complexity scatters across callers, it was earning its keep.
3. **Interface as test surface:** Tests and callers exercise the same interface across the seam.
4. **Adapter rule:** One adapter is a hypothetical seam; two adapters demonstrate a real, necessary seam.

## Designing for Testability

- **Accept dependencies explicitly:** Inject dependencies or adapters rather than hardcoding instantiations.
- **Return results over side effects:** Prefer pure computations and explicit return values over hidden state mutations.
- **Narrow interface surface:** Fewer methods and simple parameters reduce test setup complexity.
