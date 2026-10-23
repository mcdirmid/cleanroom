# dsh_harness_impl scenarios

### Scenario 1 — Dispatching DeepSeek Harness role round

Given: a role dispatch directive for role_a with prompt and ready targets in workspace_dir_a.

1. The harness adapter dispatches the round.
   Observed: when a live DeepSeek Harness server is reachable, the round is dispatched over the local RPC bridge with transient retry backoff without file lock contention (failing cleanly when unreachable without attempting incompatible headless CLI resumption); when the server is absent, a role-tailored task prompt file incorporating coordinator reminders when present is written, lock availability is verified to adopt persisted sessions safely, and a DeepSeek Harness subagent process is launched with handle `dsh-task-1-role_a`.
   Realized by: the component evaluating server reachability, dispatching over the JSON-RPC bridge with backoff or launching the headless process with overlay patch parameters and session resumption flags when the desktop server is absent.

### Scenario 2 — Awaiting successful round and extracting token telemetry

Given: an active round for role_a completes with zero exit code and recorded session telemetry.

1. The harness adapter awaits round completion.
   Observed: a role round result is returned with clean status, submitted targets derived from in-memory pending differences or action records across workspace root and scoped cleanroom logs, scraped and persisted session identifier for continuity (reset upon failed outcomes, preserved across blamed rounds), and token telemetry reflecting input and output tokens.
   Realized by: telemetry extraction delegated to dsh_telemetry, session id extraction and file persistence, discovering submitted targets from in-memory pending diffs and candidate cleanroom logs across workspace root and scoped directories matching change, clean, submitted, and audit records, and querying event streams or session storage archives for token counts.

### Scenario 3 — Handling blamed targets from blame buffer and workspace log

Given: an active round for role_a writes culprit targets into `.cleanroom_blame_buffer.json` or records blamed targets in candidate cleanroom logs.

1. The harness adapter awaits round completion.
   Observed: a role round result is returned with blamed status and blamed targets populated from the blame buffer and candidate cleanroom logs across workspace root and scoped directories.
   Realized by: the component's blame buffer reader and workspace log scanner loading targets from `.cleanroom_blame_buffer.json` and discovering blame entries recorded in candidate cleanroom logs across workspace root and scoped directories.

### Scenario 4 — Terminating timed out DeepSeek Harness rounds when explicitly configured

Given: a DeepSeek Harness subagent process exceeds the configured timeout duration when an explicit timeout limit is specified.

1. The harness adapter enforces the timeout.
   Observed: the active process is terminated and a role round result with failed status is returned.
   Realized by: the component's timeout guard sending termination signals to the running subprocess.

### Scenario 5 — Non-blocking polling without mandatory execution timeout

Given: an active DeepSeek Harness subagent process executes with default configuration without a timeout limit.

1. The harness adapter polls the active process.
   Observed: running processes return none without termination, and completed processes return final round results.
   Realized by: the component's non-blocking process polling checking process termination without raising TimeoutExpired.

### Scenario 6 — Returning unresolved status when zero targets submitted or blamed

Given: an active DeepSeek Harness subagent process terminates without submitting any targets and without writing to the blame buffer or recording blame defects in the cleanroom log.

1. The harness adapter awaits round completion.
   Observed: a role round result is returned with unresolved status and empty submitted and blamed target sequences.
   Realized by: the component's buffer diffing assigning unresolved status when both submitted and blamed targets are empty.

### Scenario 7 — Registering DeepSeek Harness adapter factory

Given: an agent session with an active harness registry.

1. The harness manager initializes.
   Observed: the DeepSeek Harness adapter factory is installed in the harness registry under platform name dsh.
   Realized by: the component's harness manager querying the harness registry singleton and installing its adapter factory during initialization.

### Scenario 8 — Calculating incremental round token telemetry across persistent session rounds

Given: consecutive rounds executing within the same persistent DeepSeek Harness session with cumulative session token counters.

1. The harness adapter awaits round completion.
   Observed: each completed role round result reports incremental round token deltas rather than cumulative session totals, preventing double-counting across waves.
   Realized by: the harness adapter tracking session token baselines, computing incremental deltas against prior session totals, and updating baselines or evicting on failure.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-21T01:00:00Z
CHANGE: Add scenario for calculating incremental round token telemetry across persistent session rounds
-->
