# Concrete scenarios for dependency_solver_impl implementation

## Reused from the interface

### Scenario 1 — Package repository registration and sorted retrieval

Given: A newly initialized package repository.

1. Register package release `pkg_a` at version `1.0.0` and release `pkg_a` at version `1.2.0`.
Observed: Package `pkg_a` is present in the repository.
Realized by: Inserting release objects into the internal package registry map keyed by package name.

2. Retrieve package releases for `pkg_a`.
Observed: The produced release sequence has version `1.2.0` followed by version `1.0.0`.
Realized by: Sorting candidate releases using the version engine precedence comparison from semver_core in descending order.

### Scenario 2 — Backtracking resolution of diamond dependencies

Given: A dependency solver and package repository where `app` depends on `lib_b` and `lib_c`, `lib_b` at `1.0.0` depends on `lib_d` with constraint `^1.0.0`, `lib_c` at `1.0.0` depends on `lib_d` with constraint `>=1.1.0 <2.0.0`, and `lib_d` has releases `1.0.0`, `1.1.0`, and `1.2.0`.

1. Resolve dependencies for root requirement `app` with constraint `^1.0.0`.
Observed: The produced resolution outcome selects version `1.2.0` for package `lib_d`.
Realized by: Intersecting accumulated constraints for `lib_d` into `>=1.1.0 <2.0.0` and selecting the highest satisfying release `1.2.0`.

### Scenario 3 — Unsatisfiable dependency conflict raises resolution conflict error

Given: A dependency solver and package repository where `pkg_x` at `1.0.0` requires `pkg_z` at `>=2.0.0`, and `pkg_y` at `1.0.0` requires `pkg_z` at `<2.0.0`.

1. Resolve dependencies for root requirements `pkg_x` at `^1.0.0` and `pkg_y` at `^1.0.0`.
Observed: A resolution conflict error is raised identifying conflicting package `pkg_z`.
Realized by: Detecting empty constraint intersection between `>=2.0.0` and `<2.0.0` during backtracking search, formatting the conflict derivation trail, and raising resolution conflict error.

2. Resolve dependencies for root requirement on unregistered package `pkg_missing` at `^1.0.0`.
Observed: A resolution conflict error is raised identifying conflicting package `pkg_missing` without raising package not found error.
Realized by: Identifying that unregistered package `pkg_missing` has zero viable candidate releases, adding it to the conflict trail, and raising resolution conflict error upon search exhaustion.

## Implementation-only

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Author dependency_solver_impl implementation concrete scenarios
-->
