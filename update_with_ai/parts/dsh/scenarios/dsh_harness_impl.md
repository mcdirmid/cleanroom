<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness_impl scenarios
CODE_HASH: 8e0c6626c378
-->

# dsh_harness_impl scenarios

### Scenario 1 — Dispatching DeepSeek Harness role turn

Given: a role dispatch directive for role_a with prompt and ready targets in workspace_dir_a.

1. The harness adapter dispatches the turn.
   Observed: a task prompt file is written and a DeepSeek Harness subagent process is launched with handle `dsh-task-1-role_a`.
   Realized by: the component's process launcher writing the prompt file and executing the dsh headless command with overlay patch parameters.

### Scenario 2 — Awaiting successful turn and extracting token telemetry

Given: an active turn for role_a completes with zero exit code and recorded session telemetry.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with clean status, submitted targets, and token telemetry reflecting input and output tokens.
   Realized by: the component's telemetry parser querying event streams or session storage archives for token counts.

### Scenario 3 — Handling blamed targets from blame buffer

Given: an active turn for role_a writes culprit targets into `.cleanroom_blame_buffer.json`.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with blamed status and blamed targets populated.
   Realized by: the component's blame buffer reader loading targets from `.cleanroom_blame_buffer.json`.

### Scenario 4 — Terminating timed out DeepSeek Harness turns when explicitly configured

Given: a DeepSeek Harness subagent process exceeds the configured timeout duration when an explicit timeout limit is specified.

1. The harness adapter enforces the timeout.
   Observed: the active process is terminated and a role turn result with failed status is returned.
   Realized by: the component's timeout guard sending termination signals to the running subprocess.

### Scenario 5 — Non-blocking polling without mandatory execution timeout

Given: an active DeepSeek Harness subagent process executes with default configuration without a timeout limit.

1. The harness adapter polls the active process.
   Observed: running processes return none without termination, and completed processes return final turn results.
   Realized by: the component's non-blocking process polling checking process termination without raising TimeoutExpired.
