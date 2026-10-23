# dsh_telemetry interface component

## Intent

Accurate accounting of token consumption and live session visibility across autonomous multi-agent runs requires structured event inspection, decompression of session archives, and background synchronization with Desktop GUI tools. Coupling this event extraction and SQLite/RPC bridge logic directly into process execution inflates harness lifecycle adapters and complicates isolated testing of rate-card calculations and desktop notifications. The dsh_telemetry interface component establishes dedicated contracts for parsing stdout JSON events, querying compressed zstd session files, evaluating model rate-card pricing, and synchronizing workspace sessions to the Desktop application.

## Factored Contracts

### Typing

- A dsh token metrics record holds uncached prompt tokens, cached prompt tokens, completion tokens, total tokens, model name, and monetary cost in USD.
- A dsh rpc round status record holds active execution status, completed status, failure error details, and cumulative token metrics parsed from DeepSeek Harness JSON-RPC round events.
- An agent session's dsh telemetry parser extracts token metrics from event streams or session storage archives, calculates token expenditure, and synchronizes active sessions with the DeepSeek Harness Desktop application.

### Contracts

- The telemetry parser parses JSON stream events or queries session storage archives to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The telemetry parser synchronizes sessions and workspace identity into DeepSeek Harness Desktop storage and notifies live GUI applications over local RPC. [sync_desktop_sessions]
- The telemetry parser evaluates whether an active DeepSeek Harness Desktop application or background server is reachable over the local RPC bridge. [eval_dsh_server_available]
- The telemetry parser dispatches role rounds over the local RPC bridge by ensuring workspace registration, creating or resuming sessions, and enqueueing prompt tasks. [dispatch_dsh_round_rpc]
- The telemetry parser polls active round status over the local RPC bridge until round quiescence. [poll_dsh_round_rpc]

### Woven Contracts

- When parsing session telemetry or tracking active runs, the telemetry parser queries metrics from event streams or storage archives, applies model pricing rates, falls back to text logs, and synchronizes desktop sessions. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, sync_desktop_sessions]
- When coordinating live round execution, the telemetry parser evaluates server reachability, dispatches role rounds over the local RPC bridge, and polls round status until completion. [eval_dsh_server_available, dispatch_dsh_round_rpc, poll_dsh_round_rpc]

## Grounding

### Knowledge Provisions

- DeepSeek Harness session storage archive parsing, rate card calculation, and Desktop application synchronization services. [dsh_telemetry_services]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]
- DeepSeek Harness session storage parsing and desktop sync mechanics.
  - Deferred: Provided by dsh telemetry implementation.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:55:00Z
CHANGE: Author dsh_telemetry planning specification
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
