<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-13T20:00:00Z
CHANGE: author dsh_harness_impl scenarios
CODE_HASH: 7f0712377f91
-->

# dsh_harness_impl scenarios

### Scenario 1 — Dispatching DeepSeek Harness role turn

Given: a role dispatch directive for role_a with prompt and ready targets in workspace_dir_a.

1. The harness adapter dispatches the turn.
   Observed: a role-tailored task prompt file is written, lock availability is verified to adopt persisted sessions safely, and a DeepSeek Harness subagent process is launched with handle `dsh-task-1-role_a`.
   Realized by: the component's process launcher writing the role-tailored prompt file, verifying non-blocking session locks, and executing the dsh headless command with overlay patch parameters and session resumption flags.

### Scenario 2 — Awaiting successful turn and extracting token telemetry

Given: an active turn for role_a completes with zero exit code and recorded session telemetry.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with clean status, submitted targets, scraped and persisted session identifier for continuity, and token telemetry reflecting input and output tokens.
   Realized by: telemetry extraction delegated to dsh_telemetry, session id extraction and file persistence, querying event streams or session storage archives for token counts.

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

### Scenario 6 — Returning unresolved status when zero targets submitted or blamed

Given: an active DeepSeek Harness subagent process terminates without submitting any targets and without writing to the blame buffer.

1. The harness adapter awaits turn completion.
   Observed: a role turn result is returned with unresolved status and empty submitted and blamed target sequences.
   Realized by: the component's buffer diffing assigning unresolved status when both submitted and blamed targets are empty.

### Scenario 7 — Registering DeepSeek Harness adapter factory

Given: an agent session with an active harness registry.

1. The harness manager initializes.
   Observed: the DeepSeek Harness adapter factory is installed in the harness registry under platform name dsh.
   Realized by: the component's harness manager querying the harness registry singleton and installing its adapter factory during initialization.
