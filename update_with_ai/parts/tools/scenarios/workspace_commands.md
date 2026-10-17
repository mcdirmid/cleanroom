<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T17:50:00Z
CHANGE: Define workspace_commands interface scenarios
CODE_HASH: ff1a29323e5f
-->

# Concrete scenarios for `workspace_commands` (interface)

## Scenario 1 — Executing get_work command

Given: an active role workspace with no dirty pending work and one ready target.

1. The caller executes `run_get_work` for the active role.
   Observed: the handler presents the ready target, records it into pending work, formats actionable guidance, and returns exit code 0.

2. The caller executes `run_get_work` again while the assigned target remains dirty.
   Observed: the handler rejects execution, reporting that pending targets remain dirty, and returns exit code 1.

## Scenario 2 — Executing check_files command

Given: an active role workspace with a missing target file for a role declaring source patterns and upstream dependencies.

1. The caller executes `run_check_files`.
   Observed: the handler regenerates the missing target from its starter template, executes verification linters, and returns the verification exit code.

## Scenario 3 — Executing submit command

Given: an active role workspace with a modified target passing verification.

1. The caller executes `run_submit` with a producer change summary.
   Observed: the handler validates the submission, appends a record to the cleanroom log in both the canonical repository and local workspace, clears the target from pending work, and returns exit code 0.

2. The caller executes `run_submit` when verification checks fail.
   Observed: the handler rejects submission and returns a non-zero exit code.

## Scenario 4 — Executing blame and fail commands

Given: an active role workspace with a pending culprit target.

1. The caller executes `run_blame` with a valid single-paragraph critique.
   Observed: the handler delegates blame attribution, appends a blame record to the cleanroom log in both the canonical repository and local workspace, clears pending work, and returns exit code 0.

2. The caller executes `run_fail` with a failure diagnostic.
   Observed: the handler records the failure diagnostic, clears pending work, and returns exit code 0.

## Scenario 5 — Executing coverage command

Given: an active role workspace with implementation and test targets.

1. The caller executes `run_coverage`.
   Observed: the handler evaluates statement coverage against the target threshold, prints diagnostic span reports, and returns the coverage exit code.

## Scenario 6 — Executing commission and refresh_sys commands

Given: an active Cleanroom repository directory.

1. The caller executes `run_commission` for a declared role.
   Observed: the handler provisions the isolated role workspace, copies required contracts, and returns exit code 0.

2. The caller executes `run_refresh_sys`.
   Observed: the handler recopies system configuration files, bin utilities, and companion guides into active role workspaces, returning exit code 0.
