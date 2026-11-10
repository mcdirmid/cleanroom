# dsh_telemetry_impl implementation component

imports: session, dsh_ext
implements: dsh_telemetry

## Purpose

The dsh_telemetry_impl implementation component realizes token metric parsing from DeepSeek Harness event streams and session storage archives, rate card evaluation, and remote JSON-RPC round dispatch via the DeepSeek Harness Web loopback bridge.

Harvesting token telemetry requires parsing JSON stream events from headless dsh runs or decompressing session.v4.jsonl.zstd archives from local storage when real-time streams are truncated. In addition, lockless round execution and streaming visibility require routing round execution through the central DeepSeek Harness Web loopback bridge. The dsh_telemetry_impl implementation component realizes structured metric extraction, regex fallback matching, multi-model pricing calculation, and local JSON-RPC round dispatch.

**Out of scope:** The dsh_telemetry_impl implementation component does not partition topological waves, compute dirty targets, or manage round timeouts; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to dsh_ext.

## Types and Behavior

The dsh telemetry parser realizes token metric extraction and Web JSON-RPC round dispatch.

The dsh telemetry parser:

- Parses JSON event lines from stdout streams, extracting input tokens, cache read tokens, and output tokens.

- Falls back to pattern matching over log text when structured JSON usage objects are absent.

- Computes monetary cost in USD by applying rate cards across frontier and local model families.

- Locates session storage directories corresponding to workspace directories, decompressing session.v4.jsonl.zstd archives or reading plain log files.

- Discovers active DeepSeek Harness Web loopback bridge endpoints from bridge configuration.

- Submits role round prompts to the DeepSeek Harness Web loopback bridge over JSON-RPC, returning active task handles, creating or adopting sessions directly in their physical role workspace directory without workspace folder registration, setting the session title to capture scope and role (e.g. `[<scope>] <role>`), resolving declared model configuration profiles against model configuration definitions discovered in workspace ancestors, working directories, user configuration, or repository hierarchy and mapping local MLX providers to oMLX endpoints. Dispatches role rounds as independent top-level sessions with unique task names labeled `[<scope>] <role>` under Ungrouped without container attachment or workspace folder registration, providing direct conversation visibility and manual interactivity.

- Renames conversation titles on DeepSeek Harness Web bridge.

- Deletes sessions from DeepSeek Harness Web bridge.

- Discovers and deletes existing conversations associated with a target directory scope (e.g. deleting all conversations containing `[<scope>]` such as `[benchmark_N]` in their title) across DeepSeek Harness Web bridge.

- Polls round execution status and extracts cumulative token counts from JSON-RPC status responses or bridge wait results until round completion, recognizing dictionary outcomes with completed or errored keys alongside terminal string statuses, and marking missing workers completed with error when absent from the active worker registry beyond an initial grace period.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-10T18:00:00Z
CHANGE: Remove legacy DSH Desktop references; consolidate on DSH Web bridge
SPEC_QA_AUDIT: 2026-10-19T22:33:00Z
-->
