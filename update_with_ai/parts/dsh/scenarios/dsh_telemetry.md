<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:55:00Z
CHANGE: Author dsh_telemetry concrete scenarios
CODE_HASH: 9f9a8f3674f2
-->

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
   Observed: the workspace entry in `workspace.json` and session projcache JSON are created or updated with the role turn title and start timestamp.
