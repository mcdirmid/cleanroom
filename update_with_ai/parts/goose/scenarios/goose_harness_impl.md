<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T12:00:00Z
CHANGE: update goose_harness_impl scenarios for non-blocking polling and timeout elimination
CODE_HASH: a42022272cb5
-->

# goose_harness_impl scenarios

### Scenario 1 — Dispatching Goose role turn

Given: a role dispatch directive for role_a with prompt and ready targets in workspace_dir_a.

1. The harness adapter dispatches the turn.
   Observed: a task prompt file is written and a Goose subagent process is launched with handle `goose-task-1-role_a`.
   Realized by: the component's process launcher writing the prompt file and executing the Goose command with compaction environment settings.

### Scenario 2 — Awaiting successful turn and extracting token telemetry

Given: an active turn for role_a completes with zero exit code and recorded session telemetry.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with clean status, submitted targets, and token telemetry reflecting input and output tokens.
   Realized by: the component's telemetry parser querying the SQLite database or parsing logs for token counts.

### Scenario 3 — Handling blamed targets from blame buffer

Given: an active turn for role_a writes culprit targets into `.cleanroom_blame_buffer.json`.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with blamed status and blamed targets populated.
   Realized by: the component's blame buffer reader loading targets from `.cleanroom_blame_buffer.json`.

### Scenario 4 — Terminating timed out Goose turns when explicitly configured

Given: a Goose subagent process exceeds the configured timeout duration when an explicit timeout limit is specified.

1. The harness adapter enforces the timeout.
   Observed: the active process is terminated and a role turn result with failed status is returned.
   Realized by: the component's timeout guard sending termination signals to the running subprocess.

### Scenario 5 — Non-blocking polling without mandatory execution timeout

Given: an active Goose subagent process executes with default configuration without a timeout limit.

1. The harness adapter polls the active process.
   Observed: running processes return none without termination, and completed processes return final turn results.
   Realized by: the component's non-blocking process polling checking process termination without raising TimeoutExpired.
