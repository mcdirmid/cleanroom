# dsh_workspace scenarios

## Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a as an author role with writable targets, and for role_b as an auditor role with zero writable targets.

1. The configurer customizes role agent documentation for role_a.
   Observed: `AGENTS.md` is updated to embed boundary constraints, permitted in-workspace shell commands and native harness tools, and workspace undo and rollback instructions (`bin/revert`).

2. The configurer customizes role agent documentation for role_b.
   Observed: `AGENTS.md` omits rollback guidance and strictly prohibits file edits and git commands.

## Scenario 2 — Generating Cordis overlay patch

Given: a provisioned role workspace directory for role_a with model and provider specifications as an author role with writable targets, and role_b as an auditor role with zero writable targets.

1. The configurer generates the overlay patch for role_a.
   Observed: a Cordis patch file in `.autofab/dsh_patch.yml` is generated configuring danger-full-access permissions, approval policy never, pre-tool lifecycle checkpoint hooks, and model routing.

2. The configurer generates the overlay patch for role_b.
   Observed: a Cordis patch file in `.autofab/dsh_patch.yml` is generated disabling `edit` and `write` tools, setting `file_policy: read-only`, and omitting pre-tool checkpoint hooks.

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
LAST_CHANGED: 2026-10-30T08:30:00Z
CHANGE: Disable edit tools and omit rollback instructions for auditor roles
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
