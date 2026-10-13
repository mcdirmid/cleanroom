<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T12:00:00Z
CHANGE: update goose_harness scenarios for non-blocking polling and timeout elimination
CODE_HASH: ec5d309e840e
-->

# goose_harness scenarios

## Scenario 1 — Dispatching Goose role turn

Given: a role dispatch directive for role_a with prompt and ready targets in workspace_dir_a.

1. The harness adapter dispatches the turn.
   Observed: a task prompt file is written and a Goose subagent process is launched with handle `goose-task-1-role_a`.

## Scenario 2 — Awaiting successful turn and extracting token telemetry

Given: an active turn for role_a completes with zero exit code and recorded session telemetry.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with clean status, submitted targets, and token telemetry reflecting input and output tokens.

## Scenario 3 — Handling blamed targets from blame buffer

Given: an active turn for role_a writes culprit targets into `.cleanroom_blame_buffer.json`.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with blamed status and blamed targets populated.

## Scenario 4 — Terminating timed out Goose turns when explicitly configured

Given: a Goose subagent process exceeds the configured timeout duration when an explicit timeout limit is specified.

1. The harness adapter enforces the timeout.
   Observed: the active process is terminated and a role turn result with failed status is returned.

## Scenario 5 — Non-blocking polling without mandatory execution timeout

Given: an active Goose subagent process executes with default configuration without a timeout limit.

1. The harness adapter polls the active process.
   Observed: running processes return none without termination, and completed processes return final turn results.
