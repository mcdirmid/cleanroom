# Concrete scenarios for `roles` (interface)

## Scenario 1 — Resolving a declared role and an undeclared role

Given: the repository has a configuration file declaring role `dev` with guide path `guides/dev.md`, source pattern `lib/{unit}.py`, role dependency `spec`, and silent role dependency `spec_qa`; and no configuration declares `unknown_role`.

1. The caller resolves the `dev` role.
   Observed: the resolved definition identifies `dev`, reports guide path `guides/dev.md`, source pattern `lib/{unit}.py`, role dependencies `['spec']`, and silent role dependencies `['spec_qa']`.

2. The caller resolves the `unknown_role` role.
   Observed: resolution fails explicitly with a KeyError, naming `unknown_role`.

## Scenario 2 — Rejecting invalid dependency configurations

Given: a configuration file attempts to declare role `bad_role` where an auditor role `audit_role` is listed under `role_deps` instead of `silent_role_deps`.

1. The caller attempts to resolve `bad_role`.
   Observed: resolution fails explicitly with a ValueError, stating that auditor roles can only be declared under silent role dependencies.

## Scenario 3 — Resolving qualified role addresses and methodology bindings

Given: a repository package `//subpkg` declares methodology `//tools/cleanroom` with role `builder` having role address `//subpkg:builder`.

1. The caller resolves `//subpkg:builder`.
   Observed: the resolved definition identifies `builder` and reports role address `//subpkg:builder`.

## Scenario 4 — Resolving multi-pattern roles declaring source patterns

Given: a role configuration declares role `baseline_a` with source patterns `['{unit_dir}/lib_a/{unit_name}.py', '{unit_dir}/tests_a/{unit_name}_fixed_test.py']`.

1. The caller resolves `baseline_a`.
   Observed: the resolved definition reports `src_patterns` containing both patterns, `src_pattern` matching the first pattern, and writable file patterns containing globs for both patterns.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-31T20:47:00Z
CHANGE: Add scenario for multi-pattern role resolution
-->
