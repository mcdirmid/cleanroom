# Concrete scenarios for `dsh_telemetry` (interface)

## Scenario 1 — Parsing structured stream text for token metrics

Given: a process execution log containing JSON-formatted event stream records with usage information.

1. The telemetry parser parses the stream text.
   Observed: a DshSessionTokenMetrics record is produced with accurate input_tokens, cached_tokens, output_tokens, total_tokens, and computed cost_usd.

## Scenario 2 — Fallback parsing of plain text logs

Given: an execution log containing plain text token printouts without JSON envelopes.

1. The telemetry parser parses the log text.
   Observed: regex pattern matching extracts input, cached, and output token counts, calculating total tokens and monetary cost.

## Scenario 3 — Parsing compressed session storage archives

Given: a DeepSeek Harness session storage directory containing a compressed `session.v4.jsonl.zstd` archive for a workspace.

1. The telemetry parser parses session storage for the workspace.
   Observed: the archive is located and decompressed, and the session token metrics are extracted.

## Scenario 4 — Synchronizing session into desktop storage

Given: a live workspace and session directory.

1. The telemetry parser synchronizes the session with desktop storage.
   Observed: the session projcache JSON is created or updated with the scope and role as title and start timestamp without creating per-role workspace records.

## Scenario 5 — Evaluating desktop server reachability and dispatching round over RPC

Given: an active DeepSeek Harness server or Desktop application listening on a local port with valid authentication cookies.

1. The telemetry parser evaluates server reachability.
   Observed: reachability is confirmed.
1. The telemetry parser dispatches a role round with workspace directory, role name, task prompt, and directory scope.
   Observed: the round is accepted by the server over the JSON-RPC bridge with session titled with scope and role directly within the role workspace directory, and a task handle is returned.

## Scenario 6 — Polling active RPC round status until completion

Given: a task handle representing an active role round dispatched over the RPC bridge.

1. The telemetry parser polls round status.
   Observed: a DshRpcRoundStatus record is returned indicating execution state and accumulated token usage.

## Scenario 7 — Renaming, deleting, and cleaning up scope sessions

Given: an active DeepSeek Harness Web bridge or Desktop server with existing sessions.

1. The telemetry parser renames a session by identifier.
   Observed: the session title is updated to the proposed title.
1. The telemetry parser cleans up conversations matching a directory scope.
   Observed: all sessions containing `[<scope>]` in their title are deleted from the server.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-09T23:32:00Z
CHANGE: Add session renaming, deletion, and scope conversation cleanup operations
-->
