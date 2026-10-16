<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:55:00Z
CHANGE: Define workspace_stub_impl concrete scenarios
CODE_HASH: 14a8d2f31bcb
-->

# Concrete scenarios for `workspace_stub_impl` (implementation)

## Scenario 1 — AST test stub generation and validation

Given: a `.pyi` file declaring an interface protocol with operations.

1. The synthesizer parses the AST, extracts function defs, and writes the test stub module.
   Observed: the destination file begins with the `CLEANROOM TEST STUB v4` header and functions raise `NotImplementedError("Cleanroom Test Stub: Behavior specified in .pyi")`.

2. The caller inspects `is_valid_test_stub` on the destination file.
   Observed: returns true.

## Scenario 2 — Stub synchronization timestamp check

Given: a destination test stub file whose timestamp is older than the source `.pyi` file.

1. The synthesizer executes `sync_all_stub_deps`.
   Observed: the destination stub is re-generated with updated signatures and permissions set to read-only (`0o444`).
