<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness scenarios
CODE_HASH: aab023d783f0
-->

# dsh_harness scenarios

## Scenario 1 — Dispatching DeepSeek Harness role turn

Given: a role dispatch directive for role_a with prompt and ready targets in workspace_dir_a.

1. The harness adapter dispatches the turn.
   Observed: when a live DeepSeek Harness server is reachable, the turn is dispatched over the local RPC bridge without file lock contention; when unreachable, a task prompt file is written and a headless DeepSeek Harness process is launched with handle `dsh-task-1-role_a`.

## Scenario 2 — Awaiting successful turn and extracting token telemetry

Given: an active turn for role_a completes successfully via the RPC bridge or process execution with recorded session telemetry.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with clean status, submitted targets, and token telemetry reflecting input and output tokens.

## Scenario 3 — Handling blamed targets from blame buffer

Given: an active turn for role_a writes culprit targets into `.cleanroom_blame_buffer.json`.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with blamed status and blamed targets populated.

## Scenario 4 — Terminating timed out DeepSeek Harness turns when explicitly configured

Given: a DeepSeek Harness subagent process exceeds the configured timeout duration when an explicit timeout limit is specified.

1. The harness adapter enforces the timeout.
   Observed: the active process is terminated and a role turn result with failed status is returned.

## Scenario 5 — Non-blocking polling without mandatory execution timeout

Given: an active DeepSeek Harness subagent process executes with default configuration without a timeout limit.

1. The harness adapter polls the active process.
   Observed: running processes return none without termination, and completed processes return final turn results.

## Scenario 6 — Returning unresolved status when zero targets submitted or blamed

Given: an active DeepSeek Harness subagent process terminates without submitting any targets and without writing to the blame buffer.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with unresolved status and empty submitted and blamed target sequences.

## Scenario 7 — Registering DeepSeek Harness adapter factory

Given: an agent session with an active harness registry.

1. The harness manager initializes.
   Observed: the DeepSeek Harness adapter factory is installed in the harness registry under platform name dsh.
