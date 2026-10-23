# dsh_telemetry_impl implementation component

imports: session, dsh_ext
implements: dsh_telemetry

## Purpose

The dsh_telemetry_impl implementation component realizes token metric parsing from DeepSeek Harness event streams and session storage archives, rate card evaluation, desktop session synchronization, and remote JSON-RPC round dispatch.

Harvesting token telemetry requires parsing JSON stream events from headless dsh runs or decompressing session.v4.jsonl.zstd archives from local storage when real-time streams are truncated. In addition, desktop visibility and lockless round execution require synchronizing session records into Chromium storage, authenticating RPC calls via local cookie tokens, and routing round execution through the central application server. The dsh_telemetry_impl implementation component realizes structured metric extraction, regex fallback matching, multi-model pricing calculation, and local JSON-RPC round dispatch.

**Out of scope:** The dsh_telemetry_impl implementation component does not partition topological waves, compute dirty targets, or manage round timeouts; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to dsh_ext.

## Types and Behavior

The dsh telemetry parser realizes token metric extraction, desktop synchronization, and JSON-RPC round dispatch.

The dsh telemetry parser:

- Parses JSON event lines from stdout streams, extracting input tokens, cache read tokens, and output tokens.

- Falls back to pattern matching over log text when structured JSON usage objects are absent.

- Computes monetary cost in USD by applying rate cards across frontier and local model families.

- Locates session storage directories corresponding to workspace directories, decompressing session.v4.jsonl.zstd archives or reading plain log files.

- Synchronizes workspace records and session identity titles into desktop storage files and communicates session creation events to running desktop applications over local RPC bridges.

- Discovers active desktop application ports and authentication cookies from application cookies storage opened in read-only immutable mode.

- Submits role round prompts to the central desktop runtime over the local JSON-RPC bridge, returning active task handles, resolving declared model configuration profiles against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy and mapping local MLX providers to oMLX endpoints.

- Polls round execution status and extracts cumulative token counts from JSON-RPC status responses until round completion.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-19T22:33:00Z
CHANGE: support user global model configuration and normalize local MLX providers to oMLX endpoints in RPC model selection
SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
-->
