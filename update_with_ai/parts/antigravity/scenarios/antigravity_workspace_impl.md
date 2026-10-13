<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_workspace_impl scenarios
CODE_HASH: 35707a983716
-->

# antigravity_workspace_impl scenarios

### Scenario 1 — Generating workspace isolation rules

Given: a newly commissioned role workspace directory for role_a in scope_a.

1. The configurer writes isolation rules into the workspace.
   Observed: isolation rules are created inside the role workspace, forbidding edits outside the workspace directory.
   Realized by: the component's file writing routine formatting boundary rules into `.agents/rules/isolation.md`.

### Scenario 2 — Generating role guidance documentation

Given: a commissioned role workspace with active verification gates.

1. The configurer writes role guidance documentation.
   Observed: instructions directing the agent to use local bin scripts for acquiring and submitting work are written to the workspace.
   Realized by: the component's documentation generation creating role guidance referencing local runner binaries.

### Scenario 3 — Reporting configured confinement boundaries

Given: a configured role workspace with isolation files.

1. The configurer inspects the configured workspace.
   Observed: a confinement report lists all generated boundary file paths and reports clean confinement status.
   Realized by: the component's report synthesis constructing a confinement report from generated files.
