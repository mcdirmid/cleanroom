# dsh_telemetry interface component

imports: session

## Purpose

The dsh_telemetry interface component defines data types and operational contracts for harvesting model token usage, parsing session storage archives, and managing execution sessions with the DeepSeek Harness Web environment.

Accurate accounting of token consumption and live session visibility across autonomous multi-agent runs requires structured event inspection, decompression of session archives, and background synchronization with Web bridge tools. Coupling this event extraction and bridge logic directly into process execution inflates harness lifecycle adapters and complicates isolated testing of rate-card calculations and session lifecycle notifications. The dsh_telemetry interface component establishes dedicated contracts for parsing stdout JSON events, querying compressed zstd session files, evaluating model rate-card pricing, and managing workspace sessions via the Web loopback bridge.

**Out of scope:** The dsh_telemetry interface component does not spawn worker subprocesses, manage process timeout intervals, or compute dirty DAG queues; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *dsh token metrics* record captures uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary expenditure in USD parsed from DeepSeek Harness session storage or event streams.

A *dsh rpc round status* record captures active execution status, completed status, failure error details, and cumulative token metrics parsed from DeepSeek Harness JSON-RPC round events.

The *dsh telemetry parser* of an agent session extracts token metrics from event streams or session storage archives, calculates token expenditure, and manages active sessions with the DeepSeek Harness Web environment.

The dsh telemetry parser:

- Parses stdout JSON event streams or fallback log text for input, cached, and output token usage, computing monetary expenditure via model rate cards.

- Queries session storage archives beneath the configured sessions directory, decompressing zstd archives to extract session token counts.

- Evaluates whether an active DeepSeek Harness Web loopback bridge is reachable.

- Dispatches role rounds over the local RPC bridge by creating or resuming sessions directly within their physical role workspace directory and naming conversation titles with the target scope and role (e.g. `[<scope>] <role>`), enqueueing prompt tasks without local file lock contention, and avoiding registering per-role workspace folders.

- Renames conversation titles on DeepSeek Harness Web bridge.

- Deletes existing sessions from DeepSeek Harness Web bridge.

- Discovers and deletes existing conversations associated with a target directory scope (e.g. deleting all conversations containing `[<scope>]` such as `[benchmark_N]` in their title) across DeepSeek Harness Web bridge.

- Polls active round status over the local RPC bridge until round quiescence.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-10T18:00:00Z
CHANGE: Remove legacy DSH Desktop references; consolidate on DSH Web bridge
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
