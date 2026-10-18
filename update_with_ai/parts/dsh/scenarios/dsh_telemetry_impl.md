<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:55:00Z
CHANGE: Author dsh_telemetry_impl concrete scenarios
CODE_HASH: c196301d8383
-->

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

### Scenario 4 — Synchronizing session into desktop storage

Given: a live workspace and session directory.

1. The telemetry parser synchronizes the session with desktop storage.
   Observed: the workspace entry in `workspace.json` and session projcache JSON are created or updated with the role turn title and start timestamp.
   Realized by: the component's desktop synchronizer writing projcache files and sending RPC requests to local Desktop endpoints.

### Scenario 5 — Evaluating desktop server reachability and dispatching turn over RPC

Given: an active DeepSeek Harness server or Desktop application listening on a local port with valid authentication cookies.

1. The telemetry parser evaluates server reachability.
   Observed: reachability is confirmed.
   Realized by: probing the active application port and verifying cookie authentication.
2. The telemetry parser dispatches a role turn with workspace directory, role name, and task prompt.
   Observed: the turn is accepted by the server over the JSON-RPC bridge and a task handle is returned.
   Realized by: executing workspace/create, session/create, and session/prompt RPC requests.

### Scenario 6 — Polling active RPC turn status until completion

Given: a task handle representing an active role turn dispatched over the RPC bridge.

1. The telemetry parser polls turn status.
   Observed: a DshRpcTurnStatus record is returned indicating execution state and accumulated token usage.
   Realized by: querying session status and event records over the JSON-RPC bridge.
