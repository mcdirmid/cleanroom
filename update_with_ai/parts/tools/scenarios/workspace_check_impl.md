<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:25:00Z
CHANGE: Define workspace_check_impl concrete scenarios
CODE_HASH: 9b41a86ccb40
-->

# Concrete scenarios for `workspace_check_impl` (implementation)

## Scenario 1 — Work discovery with pending dirty target blocking

Given: an active role workspace with a pending dirty target recorded in the buffer.

1. The caller runs `run_get_work`.
   Observed: returns exit code 1 and outputs error requiring completion of the pending target.

## Scenario 2 — File verification with starter template regeneration

Given: a regenerable role whose target file is missing from disk.

1. The caller runs `run_check_files`.
   Observed: regenerates target from starter template and executes verification commands.
