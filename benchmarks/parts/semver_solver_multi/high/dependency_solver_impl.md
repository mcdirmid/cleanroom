# dependency_solver_impl implementation component

imports: backtracking_solver_ext, semver_core, semver_range
implements: dependency_solver

## Purpose

The dependency_solver_impl implementation component realizes concrete package repositories, release history indexes, and backtracking dependency resolution engines.

Implementing deterministic package resolution requires systematic indexing of releases by version precedence, fast dependency lookup, and backtracking search that recovers from diamond dependency conflicts. Without disciplined search state tracking and conflict recording, dependency resolution suffers from exponential search times, infinite loops, and cryptic failure messages. The dependency_solver_impl implementation component provides index-backed release retrieval, depth-first backtracking search, and structured conflict explanation generation.

**Out of scope:** The dependency_solver_impl implementation component does not parse raw version strings or compile range expressions, nor does it download package archives from remote network registries, unpack tarballs, or install files into filesystem virtual environments.

## Types and Behavior

A system's *concrete package repository* realizes the package repository protocol using an internal map of package names to lists of package releases. When registering a release, the repository inserts the release and sorts the release list in descending version precedence order.

A system's *concrete dependency solver* realizes the dependency solver protocol using recursive depth-first search with backtracking. The solver accepts root dependencies and maintains a map of accumulated version constraints. At each step, the solver selects the unassigned package with the fewest satisfying candidate releases according to the Minimum Remaining Values heuristic. Candidates are explored in descending version precedence order.

When an assignment violates constraints or introduces an unsatisfiable dependency, the solver records the conflict in a diagnostic trail and backtracks to evaluate alternative releases. When all possibilities are exhausted without a complete assignment, the solver compiles the conflict trail into an explanation and raises resolution conflict error. If resolution succeeds, the solver compiles selected releases into a resolution outcome.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-30T19:00:00Z
LAST_CHANGED: 2026-10-30T19:00:00Z
CHANGE: Update imports to semver_core and semver_range
SPEC_QA_AUDIT: 2026-10-30T19:00:00Z
-->
