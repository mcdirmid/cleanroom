<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T11:20:00Z
CHANGE: update scenarios for AGENTS.md customization
CODE_HASH: 855990ffb94c
-->

# goose_workspace_impl scenarios

### Scenario 1 — Customizing role agent documentation with boundary constraints

Given: a provisioned role workspace directory for role_a.

1. The configurer customizes role agent documentation.
   Observed: `AGENTS.md` is written or updated with explicit isolation boundaries, tripwires, and restricted binary directives tailored for Goose.
   Realized by: the component's file writer writing `AGENTS.md` with boundary constraints.

### Scenario 2 — Emitting confinement report

Given: workspace configuration has completed for role_a in workspace_dir_a.

1. The configurer returns configuration status.
   Observed: a confinement report containing workspace_dir_a, role_a, configured file paths, and success status is returned.
   Realized by: the component's report constructor checking created files and building the report.
