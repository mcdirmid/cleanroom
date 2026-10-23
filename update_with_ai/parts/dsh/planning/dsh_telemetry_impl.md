# dsh_telemetry_impl implementation component

## Intent

Harvesting token telemetry requires parsing JSON stream events from headless dsh runs or decompressing session.v4.jsonl.zstd archives from local storage when real-time streams are truncated. In addition, desktop visibility requires synchronizing session records into Chromium storage and authenticating RPC calls via local cookie tokens. The dsh_telemetry_impl implementation component realizes structured metric extraction, regex fallback matching, multi-model pricing calculation, and local RPC desktop synchronization.

## Factored Contracts

### Typing

- The dsh telemetry parser realization implements DshTelemetryParser.

### Contracts

- The telemetry parser realization parses JSON stream events or queries session storage archives (decompressing session.v4.jsonl.zstd or reading uncompressed session.v4.jsonl) to retrieve input tokens, output tokens, and cache read tokens. [query_dsh_telemetry_metrics]
- The telemetry parser realization applies pricing rates for the active model family to calculate USD expenditures. [apply_dsh_pricing_rates]
- The telemetry parser realization parses token metrics from stdout log text when structured records are absent. [parse_log_text_fallback]
- The telemetry parser realization synchronizes workspace and session records into Desktop files and invokes Desktop RPC endpoints. [sync_desktop_sessions]
- The telemetry parser realization probes local cookie storage in immutable mode to determine if the desktop server is reachable. [eval_dsh_server_available]
- The telemetry parser realization dispatches role rounds by calling workspace/create, session/create, session/selectModel (resolving declared model profile names against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy and mapping local MLX providers to oMLX endpoints), and session/prompt over the JSON-RPC bridge. [dispatch_dsh_round_rpc]
- The telemetry parser realization polls round execution status and extracts token counts until completion. [poll_dsh_round_rpc]

### Woven Contracts

- When parsing session telemetry or recording sessions, the parser extracts metrics from event streams or storage archives, falls back to text logs, applies model pricing, and synchronizes desktop sessions. [query_dsh_telemetry_metrics, parse_log_text_fallback, apply_dsh_pricing_rates, sync_desktop_sessions, dsh_telemetry: [query_dsh_telemetry_metrics, apply_dsh_pricing_rates, parse_log_text_fallback, sync_desktop_sessions]]
- When coordinating live round execution, the parser probes server reachability, dispatches role rounds over JSON-RPC, and polls round status until completion. [eval_dsh_server_available, dispatch_dsh_round_rpc, poll_dsh_round_rpc, dsh_telemetry: [eval_dsh_server_available, dispatch_dsh_round_rpc, poll_dsh_round_rpc]]

## Grounding

### Knowledge Provisions

- DeepSeek Harness telemetry parsing and desktop synchronization mechanics. [dsh_telemetry_mechanics]

### Inherited Deferred Requirements

- DeepSeek Harness session storage parsing and desktop sync mechanics.
  - Grounded: [dsh_telemetry_mechanics]

### Knowledge Requirements

- Agent session lifecycle tier management.
  - Grounded: [session: [agent_session_tier_provision]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-19T22:33:00Z
CHANGE: align dsh_telemetry_impl planning with user configuration discovery and MLX mapping
SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
-->
