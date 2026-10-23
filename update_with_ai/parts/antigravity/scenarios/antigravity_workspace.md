# antigravity_workspace scenarios

## Scenario 1 — Generating workspace isolation rules

Given: a newly commissioned role workspace directory for role_a in scope_a.

1. The configurer writes isolation rules into the workspace.
   Observed: isolation rules are created inside the role workspace, forbidding edits outside the workspace directory.

## Scenario 2 — Generating role guidance documentation

Given: a commissioned role workspace with active verification gates.

1. The configurer writes role guidance documentation.
   Observed: instructions directing the agent to use local bin scripts for acquiring and submitting work are written to the workspace.

## Scenario 3 — Reporting configured confinement boundaries

Given: a configured role workspace with isolation files.

1. The configurer inspects the configured workspace.
   Observed: a confinement report lists all generated boundary file paths and reports clean confinement status.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_workspace scenarios
-->
