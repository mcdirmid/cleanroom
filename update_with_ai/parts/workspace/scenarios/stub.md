<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:55:00Z
CHANGE: Define stub interface scenarios
CODE_HASH: 3e93b1a5ea7e
-->

# Concrete scenarios for `stub` (interface)

## Scenario 1 — Synthesizing read-only test stubs from typing specifications

Given: a .pyi typing specification defining a class with typed methods.

1. The caller requests stub generation for the specification to a destination Python file.
   Observed: a read-only Python module is generated containing method stubs that raise NotImplementedError with exact parameter signatures, rewritten imports pointing to local workspace library stubs, and injected missing interface method signatures.

## Scenario 2 — Synchronizing stub role dependencies

Given: a role workspace commissioned with stub_role_deps on an upstream role whose specifications were updated.

1. The caller runs stub synchronization across the workspace.
   Observed: out-of-date test stubs are regenerated, missing stubs are created, and existing valid stubs with matching timestamps are preserved.

## Scenario 3 — Matching stub dependency file paths

Given: a candidate relative path `parts/agent/lib/foo.py` and a role definition declaring `stub_role_deps = ["lib"]`.

1. The caller queries whether the path is a stub dependency file.
   Observed: the method returns true.
