<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:25:00Z
CHANGE: Define workspace_check interface scenarios
CODE_HASH: 9f95758eedb2
-->

# Concrete scenarios for `workspace_check` (interface)

## Scenario 1 — Discovering work in an active role workspace

Given: an active role workspace with ready tasks in repository scope.

1. The caller executes `run_get_work`.
   Observed: returns exit code 1 when tasks are ready, prints assigned ready targets, and formats actionable next steps.

## Scenario 2 — Running verification checks on specified targets

Given: an active role workspace with a valid target file passing lint rules.

1. The caller executes `run_check_files`.
   Observed: returns exit code 0 when all checks pass.
