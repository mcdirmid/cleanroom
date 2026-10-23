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

## Scenario 4 — Customizing role agent documentation with model-contingent directives

Given: a provisioned role workspace directory with a local or output-constrained model specification.

1. The configurer customizes role agent documentation for a local or constrained model.
   Observed: `AGENTS.md` contains incremental authoring and payload ceiling protection directives instructing the worker to avoid monolithic tool calls.

2. The configurer customizes role agent documentation for a cloud model.
   Observed: `AGENTS.md` omits incremental authoring advice.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-20T22:12:00Z
CHANGE: author model-contingent AGENTS.md customization scenario
-->
