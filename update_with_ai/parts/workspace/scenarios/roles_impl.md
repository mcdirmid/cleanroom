<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:45:00Z
CHANGE: Define roles_impl concrete scenarios
CODE_HASH: b7787358d322
-->

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
