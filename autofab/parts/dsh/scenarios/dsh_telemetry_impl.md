# Concrete scenarios for `dsh_telemetry_impl` (implementation)

Scenarios 1 through 6 restate the caller observations of the interface scenarios and add, beside each observation, the realization that produces it.

## Reused from the interface

### Scenario 1 — Parsing structured stream text for token metrics

Given: a process execution log containing JSON-formatted event stream records with usage information.

1. The telemetry parser parses the stream text.
   Observed: a DshSessionTokenMetrics record is produced with accurate input_tokens, cached_tokens, output_tokens, total_tokens, and computed cost_usd.
   Realized by: the component's JSON stream parser extracting usage dictionaries and computing rate card expenditure.

### Scenario 2 — Fallback parsing of plain text logs

Given: an execution log containing plain text token printouts without JSON envelopes.

1. The telemetry parser parses the log text.
   Observed: regex pattern matching extracts input, cached, and output token counts, calculating total tokens and monetary cost.
   Realized by: the component's regex pattern matching fallback inspecting log lines.

### Scenario 3 — Parsing compressed or uncompressed session storage archives

Given: a DeepSeek Harness session storage directory containing a compressed `session.v4.jsonl.zstd` archive or uncompressed `session.v4.jsonl` for a workspace.

1. The telemetry parser parses session storage for the workspace.
   Observed: the archive is located and decompressed (or read directly if uncompressed), and the session token metrics are extracted.
   Realized by: the component's session archive locator invoking zstd decompression or plain jsonl reading and parsing session records.

### Scenario 4 — Evaluating Web loopback bridge reachability

Given: an active DeepSeek Harness Web loopback bridge.

1. The telemetry parser evaluates server reachability.
   Observed: reachability is confirmed via the Web loopback bridge endpoint.
   Realized by: discovering active Web bridge endpoint from bridge configuration.

### Scenario 5 — Dispatching round over DSH Web bridge as ungrouped session

Given: an active DeepSeek Harness Web loopback bridge.

1. The telemetry parser dispatches a role round with workspace directory, role name, task prompt, and directory scope.
   Observed: the role worker is spawned directly as an independent top-level session with a globally unique task name labeled `[<scope>] <role>` under Ungrouped without container attachment or parent session reference.
   Realized by: invoking dsh_spawn with a unique task name, formatted label, and cwd without invoking dsh_container or passing parent_session.

### Scenario 6 — Polling active RPC round status until completion

Given: a task handle representing an active role round dispatched over the RPC bridge.

1. The telemetry parser polls round status across string statuses and dictionary outcomes.
   Observed: a DshRpcRoundStatus record is returned indicating execution state and accumulated token usage, recognizing terminal outcomes in string states ('completed', 'done', 'success', 'closed', 'error', 'failed', 'aborted') or dictionary structures with 'completed' or 'errored' keys, or returning completed with error when the worker is absent from active worker listings beyond an initial grace period.
   Realized by: querying session status and event records over the JSON-RPC bridge or bridge tool endpoints.

### Scenario 7 — Renaming, deleting, and cleaning up scope sessions

Given: an active DeepSeek Harness Web bridge with existing sessions.

1. The telemetry parser renames a session by identifier.
   Observed: the session title is updated to the proposed title.
   Realized by: invoking dsh_rename_session over the Web bridge.
1. The telemetry parser cleans up conversations matching a directory scope.
   Observed: all sessions containing `[<scope>]` in their title are deleted from the server.
   Realized by: listing sessions via dsh_list_sessions, filtering by `[<scope>]` in the title, and deleting each matching session via dsh_delete_session.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-10T18:00:00Z
CHANGE: Remove legacy DSH Desktop references; consolidate on DSH Web bridge
-->
