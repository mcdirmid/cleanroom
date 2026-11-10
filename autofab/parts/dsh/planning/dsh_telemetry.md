# dsh_telemetry interface component

## Intent

Accurate accounting of token consumption and live session visibility across autonomous multi-agent runs requires structured event inspection, decompression of session archives, and background synchronization with Web bridge tools. Coupling this event extraction and bridge logic directly into process execution inflates harness lifecycle adapters and complicates isolated testing of rate-card calculations and session lifecycle notifications. The dsh_telemetry interface component establishes dedicated contracts for parsing stdout JSON events, querying compressed zstd session files, evaluating model rate-card pricing, and managing workspace sessions via the Web loopback bridge.

## Factored Contracts

### Typing

- A dsh token metrics record holds uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary cost in USD.
- A dsh rpc round status record holds active execution status, completed status, failure error details, and cumulative token metrics parsed from DeepSeek Harness JSON-RPC round events.
- An agent session's dsh telemetry parser extracts token metrics from event streams or session storage archives, calculates token expenditure, and manages active sessions with the DeepSeek Harness Web environment.

### Contracts

- The telemetry parser parses JSON stream events or queries session storage archives to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The telemetry parser evaluates whether an active DeepSeek Harness Web loopback bridge is reachable over the local RPC bridge. [eval_dsh_server_available]
- The telemetry parser dispatches role rounds over the local RPC bridge by creating or resuming sessions directly within their physical role workspace directory and naming conversation titles with the target scope and role without creating per-role workspace folders, and enqueueing prompt tasks. [dispatch_dsh_round_rpc]
- The telemetry parser renames a conversation title on DeepSeek Harness Web bridge. [rename_dsh_session]
- The telemetry parser deletes a session from DeepSeek Harness Web bridge. [delete_dsh_session]
- The telemetry parser discovers and deletes all existing conversations containing `[<scope>]` in their title from DeepSeek Harness Web bridge. [cleanup_scope_dsh_sessions]
- The telemetry parser polls active round status over the local RPC bridge until round quiescence. [poll_dsh_round_rpc]

### Woven Contracts

- When parsing session telemetry or tracking active runs, the telemetry parser queries metrics from event streams or storage archives, applies model pricing rates, and falls back to text logs. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates]
- When coordinating live round execution, the telemetry parser evaluates server reachability, dispatches role rounds over the local RPC bridge, manages session lifecycle via rename and delete, and polls round status until completion. [eval_dsh_server_available, dispatch_dsh_round_rpc, rename_dsh_session, delete_dsh_session, cleanup_scope_dsh_sessions, poll_dsh_round_rpc]

## Grounding

### Knowledge Provisions

- DeepSeek Harness session storage archive parsing, rate card calculation, and Web bridge management services. [dsh_telemetry_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]
- DeepSeek Harness session storage parsing and Web bridge mechanics.
  - Deferred: Provided by dsh telemetry implementation.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-10T18:00:00Z
CHANGE: Remove legacy DSH Desktop references; consolidate on DSH Web bridge
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
