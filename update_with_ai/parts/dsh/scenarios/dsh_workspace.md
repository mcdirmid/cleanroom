<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_workspace scenarios
CODE_HASH: c8781858c47c
-->

# dsh_workspace scenarios

## Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a.

1. The configurer customizes role agent documentation.
   Observed: `AGENTS.md` is updated or verified to restrict file mutations strictly to the workspace root and limit shell commands to the five role binaries.

## Scenario 2 — Generating Cordis overlay patch

Given: a provisioned role workspace directory for role_a with model and provider specifications.

1. The configurer generates the overlay patch.
   Observed: a Cordis patch file in `.cleanroom/dsh_patch.yml` is generated configuring danger-full-access permissions, approval policy never, and model routing.

## Scenario 3 — Emitting confinement report

Given: workspace configuration has completed for role_a in workspace_dir_a.

1. The configurer returns configuration status.
   Observed: a confinement report containing workspace_dir_a, role_a, configured file paths, and success status is returned.
