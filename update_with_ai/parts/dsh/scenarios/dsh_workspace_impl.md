<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:45:00Z
CHANGE: align dsh_workspace_impl scenarios with auditor code inspection and terminal command restrictions
CODE_HASH: 32d9f3c03497
-->

# dsh_workspace_impl scenarios

### Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a.

1. The configurer customizes role agent documentation.
   Observed: `AGENTS.md` is written or updated with explicit isolation boundaries, tripwires, restricted binary directives, and auditor rules mandating in-workspace code and change header inspection while prohibiting code edits.
   Realized by: the component's file writer writing `AGENTS.md` with boundary constraints and role-specific editing rules.

### Scenario 2 — Generating Cordis overlay patch

Given: a provisioned role workspace directory for role_a with model and provider specifications.

1. The configurer generates the overlay patch.
   Observed: a Cordis patch file in `.cleanroom/dsh_patch.yml` is generated configuring danger-full-access permissions, approval policy never, disabled task management plugins, and model routing resolving declarative model profile names against model configuration definitions.
   Realized by: the component's patch generator writing `.cleanroom/dsh_patch.yml`.

### Scenario 3 — Emitting confinement report

Given: workspace configuration has completed for role_a in workspace_dir_a.

1. The configurer returns configuration status.
   Observed: a confinement report containing workspace_dir_a, role_a, configured file paths, and success status is returned.
   Realized by: the component's report constructor checking created files and building the report.
