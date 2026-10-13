<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_workspace_impl scenarios
CODE_HASH: 72a25f148388
-->

# dsh_workspace_impl scenarios

### Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a.

1. The configurer customizes role agent documentation.
   Observed: `AGENTS.md` is written or updated with explicit isolation boundaries, tripwires, and restricted binary directives tailored for DeepSeek Harness.
   Realized by: the component's file writer writing `AGENTS.md` with boundary constraints.

### Scenario 2 — Generating Cordis overlay patch

Given: a provisioned role workspace directory for role_a with model and provider specifications.

1. The configurer generates the overlay patch.
   Observed: a Cordis patch file in `.cleanroom/dsh_patch.yml` is generated configuring danger-full-access permissions, approval policy never, and model routing.
   Realized by: the component's patch generator writing `.cleanroom/dsh_patch.yml`.

### Scenario 3 — Emitting confinement report

Given: workspace configuration has completed for role_a in workspace_dir_a.

1. The configurer returns configuration status.
   Observed: a confinement report containing workspace_dir_a, role_a, configured file paths, and success status is returned.
   Realized by: the component's report constructor checking created files and building the report.
