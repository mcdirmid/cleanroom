# dsh_telemetry_impl implementation component

## Intent

Harvesting token telemetry requires parsing JSON stream events from headless dsh runs or decompressing session.v4.jsonl.zstd archives from local storage when real-time streams are truncated. In addition, lockless round execution and streaming visibility require routing round execution through the central DeepSeek Harness Web loopback bridge. The dsh_telemetry_impl implementation component realizes structured metric extraction, regex fallback matching, multi-model pricing calculation, and local JSON-RPC round dispatch.

## Factored Contracts

### Typing

- The dsh telemetry parser realization implements DshTelemetryParser.

### Contracts

- The telemetry parser realization parses JSON stream events or queries session storage archives (decompressing session.v4.jsonl.zstd or reading uncompressed session.v4.jsonl) to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser realization applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser realization parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The telemetry parser realization checks active Web loopback bridge configuration to determine if the Web bridge is reachable. [eval_dsh_server_available]
- The telemetry parser realization dispatches role rounds by creating or adopting sessions directly within their physical role workspace directory, setting conversation name to capture scope and role (e.g. `[<scope>] <role>`), resolving declared model profile names against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy and mapping local MLX providers to oMLX endpoints, and enqueueing prompts via bridge tools over the JSON-RPC bridge without registering role workspace folders. Dispatches role rounds as independent top-level sessions with unique task names labeled `[<scope>] <role>` under Ungrouped without container attachment or workspace folder registration, providing direct conversation visibility and manual interactivity without subagent monitor dependencies. [dispatch_dsh_round_rpc]
- The telemetry parser realization renames a conversation title on DeepSeek Harness Web bridge. [rename_dsh_session]
- The telemetry parser realization deletes a session from DeepSeek Harness Web bridge. [delete_dsh_session]
- The telemetry parser realization discovers and deletes all existing conversations containing `[<scope>]` in their title from DeepSeek Harness Web bridge. [cleanup_scope_dsh_sessions]
- The telemetry parser realization polls round execution status and extracts token counts until completion, recognizing dictionary outcomes with completed or errored keys alongside terminal string statuses, and marking missing workers completed with error when absent from the active worker registry beyond an initial grace period. [poll_dsh_round_rpc]

### Woven Contracts

- When parsing session telemetry or recording sessions, the parser extracts metrics from event streams or storage archives, falls back to text logs, and applies model pricing. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, dsh_telemetry: [query_dsh_telemetry_metrics, apply_dsh_pricing_rates, parse_log_text_fallback]]
- When coordinating live round execution, the parser probes server reachability, dispatches role rounds over JSON-RPC, manages session lifecycle via rename and delete, and polls round status until completion. [eval_dsh_server_available, dispatch_dsh_round_rpc, rename_dsh_session, delete_dsh_session, cleanup_scope_dsh_sessions, poll_dsh_round_rpc, dsh_telemetry: [eval_dsh_server_available, dispatch_dsh_round_rpc, rename_dsh_session, delete_dsh_session, cleanup_scope_dsh_sessions, poll_dsh_round_rpc]]

## Grounding

### Knowledge Provisions

- DeepSeek Harness telemetry parsing and Web bridge management mechanics. [dsh_telemetry_mechanics]

### Inherited Deferred Requirements

- DeepSeek Harness session storage parsing and Web bridge mechanics.
  - Grounded: [dsh_telemetry_mechanics]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-10T18:00:00Z
CHANGE: Remove legacy DSH Desktop references; consolidate on DSH Web bridge
SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
-->
