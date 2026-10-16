<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-14T18:55:00Z
CHANGE: Author dsh_telemetry_impl implementation specification
CODE_HASH: 8452487dc2eb
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# dsh_telemetry_impl implementation component

imports: agent_session
implements: dsh_telemetry

## Purpose

The dsh_telemetry_impl implementation component realizes token metric parsing from DeepSeek Harness event streams and session storage archives, rate card evaluation, and desktop session synchronization.

Harvesting token telemetry requires parsing JSON stream events from headless dsh runs or decompressing session.v4.jsonl.zstd archives from local storage when real-time streams are truncated. In addition, desktop visibility requires synchronizing session records into Chromium storage and authenticating RPC calls via local cookie tokens. The dsh_telemetry_impl implementation component realizes structured metric extraction, regex fallback matching, multi-model pricing calculation, and local RPC desktop synchronization.

**Out of scope:** The dsh_telemetry_impl implementation component does not spawn processes, compute dirty targets, or manage turn timeouts; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; platform conventions are delegated to dsh_ext.

## Types and Behavior

The dsh telemetry parser realizes token metric extraction and desktop synchronization.

The dsh telemetry parser:

- Parses JSON event lines from stdout streams conforming to dsh_ext, extracting inputTokens, cacheReadTokens, and outputTokens.

- Falls back to regex pattern matching over log text when structured JSON usage objects are absent.

- Computes monetary cost in USD by applying rate cards across frontier and local model families.

- Locates session storage directories corresponding to workspace directories, decompressing session.v4.jsonl.zstd archives using zstd or reading plain jsonl files.

- Synchronizes workspace records and session identity titles into Desktop storage files (`workspace.json` and session projcache) and communicates session creation events to running Desktop applications over local RPC bridges.
