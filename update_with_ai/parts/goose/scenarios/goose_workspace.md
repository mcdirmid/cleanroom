<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T11:20:00Z
CHANGE: update scenarios for AGENTS.md customization
CODE_HASH: 9f8aa21308df
-->

# goose_workspace scenarios

## Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a.

1. The configurer customizes role agent documentation.
   Observed: `AGENTS.md` is updated or verified to restrict file mutations strictly to the workspace root and limit shell commands to the five role binaries.

## Scenario 2 — Emitting confinement report

Given: workspace configuration has completed for role_a in workspace_dir_a.

1. The configurer returns configuration status.
   Observed: a confinement report containing workspace_dir_a, role_a, configured file paths, and success status is returned.
