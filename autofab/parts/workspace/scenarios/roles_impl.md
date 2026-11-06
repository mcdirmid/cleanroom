# Concrete scenarios for `roles_impl` (implementation)

## Scenario 1 — Parsing TOML role configurations and caching definitions

Given: a TOML configuration file on disk declaring role `coder` with source pattern `lib/{unit}.py`.

1. The caller resolves `coder` through the role resolver.
   Observed: the resolver reads the file, parses the TOML attributes, caches the parsed mapping against file modification time, and returns the populated role definition.

2. The caller resolves `coder` a second time while the file remains untouched.
   Observed: the resolver reuses the cached role definition without re-reading the file from disk.

## Scenario 2 — Fallback to BUILD.bazel AST evaluation

Given: a repository package without a TOML configuration file, but containing a `BUILD.bazel` file containing `define_role(name="auditor", audit_tag="AUDITOR_AUDIT")`.

1. The caller resolves `auditor`.
   Observed: the resolver parses the build file AST, extracts the role attributes, marks it as an auditor role, and returns the populated role definition.

## Scenario 3 — Pipeline-aware role listing and filtering

Given: a methodology defining universal roles (`lib`), standard roles (`test`), and pretense roles (`pretense`), and a directory scope configured with `pipeline = "pretense"`.

1. The caller lists roles for the directory scope.
   Observed: the resolver discovers the active pipeline for the directory scope and returns universal and pretense roles while excluding standard roles.

2. The caller lists roles for an unconfigured directory scope without an explicit pipeline configuration.
   Observed: the resolver defaults the active pipeline to standard and returns universal and standard roles while excluding pretense roles.

3. The caller lists roles for a directory scope configured with `pipeline = "combined"`.
   Observed: the resolver returns universal, standard, and pretense roles.

## Scenario 4 — Parsing multi-pattern source declarations

Given: a TOML configuration file declaring role `baseline_a` with `src_patterns = ['{unit_dir}/lib_a/{unit_name}.py', '{unit_dir}/tests_a/{unit_name}_fixed_test.py']` and role `dependent` depending on `baseline_a`.

1. The caller resolves `baseline_a`.
   Observed: `baseline_a` has `writable_file_patterns` containing globs for both patterns, `src_patterns` containing both strings, and `src_pattern` matching the first.

2. The caller resolves `dependent`.
   Observed: `dependent` has `readonly_file_patterns` containing globs for both of `baseline_a`'s patterns.

## Scenario 5 — Parsing star feedback role dependencies

Given: a TOML configuration file declaring role `auditor_star` with `star_feedback_role_deps = ['pretense']` and `feedback_role_deps = ['lib']`.

1. The caller resolves `auditor_star`.
   Observed: `auditor_star` has `star_feedback_role_deps` containing `['pretense']` and `feedback_role_deps` containing `['lib']`.

2. The configuration file declares `star_feedback_role_deps = ['pretense']` and redundantly declares `star_role_deps = ['pretense']`.
   Observed: resolving the role fails explicitly with ValueError.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-05T11:27:00Z
CHANGE: Add scenario for star feedback role dependencies
-->
