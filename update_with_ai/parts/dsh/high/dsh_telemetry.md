# dsh_telemetry interface component

imports: session

## Purpose

The dsh_telemetry interface component defines data types and operational contracts for harvesting model token usage, parsing session storage archives, and synchronizing execution sessions with the DeepSeek Harness Desktop application.

Accurate accounting of token consumption and live session visibility across autonomous multi-agent runs requires structured event inspection, decompression of session archives, and background synchronization with Desktop GUI tools. Coupling this event extraction and SQLite/RPC bridge logic directly into process execution inflates harness lifecycle adapters and complicates isolated testing of rate-card calculations and desktop notifications. The dsh_telemetry interface component establishes dedicated contracts for parsing stdout JSON events, querying compressed zstd session files, evaluating model rate-card pricing, and synchronizing workspace sessions to the Desktop application.

**Out of scope:** The dsh_telemetry interface component does not spawn worker subprocesses, manage process timeout intervals, or compute dirty DAG queues; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *dsh token metrics* record captures uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary expenditure in USD parsed from DeepSeek Harness session storage or event streams.

A *dsh rpc round status* record captures active execution status, completed status, failure error details, and cumulative token metrics parsed from DeepSeek Harness JSON-RPC round events.

The *dsh telemetry parser* of an agent session extracts token metrics from event streams or session storage archives, calculates token expenditure, and synchronizes active sessions with the DeepSeek Harness Desktop application.

The dsh telemetry parser:

- Parses stdout JSON event streams or fallback log text for input, cached, and output token usage, computing monetary expenditure via model rate cards.

- Queries session storage archives beneath the configured sessions directory, decompressing zstd archives to extract session token counts.

- Synchronizes workspace and session identity records into DeepSeek Harness Desktop storage, notifying live Desktop GUI applications over the local RPC bridge.

- Evaluates whether an active DeepSeek Harness Desktop application or background server is reachable over the local RPC bridge.

- Dispatches role rounds over the local RPC bridge by ensuring workspace registration, creating or resuming sessions, and enqueueing prompt tasks without local file lock contention.

- Polls active round status over the local RPC bridge until round quiescence.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:55:00Z
CHANGE: Author dsh_telemetry interface specification
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
