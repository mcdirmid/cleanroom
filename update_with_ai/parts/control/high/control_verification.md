<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: c8775cab9de7
-->

# control_verification interface component

imports: agent_session, agent_node_config, dag_storage

## Purpose

The control_verification interface component defines verification check evaluation, compiler diagnostic noise filtering, and verification outcome caching across workspace targets.

Autonomous coding tasks and validation processes require dependable feedback loops to verify that generated code compiles, type-checks, and passes test suites before committing changes. Without standardized verification evaluation, raw compiler outputs flood the agent context with noisy build banners, while redundant re-executions of unchanged files waste compute. The control_verification interface component provides dual-mode verification assessment, sanitizes diagnostic output, and caches evaluation results against file hashes.

**Out of scope:** The control_verification interface component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

## Types and Behavior

A *verification result* reports whether verification checks succeeded or failed, carrying a boolean *passed* flag, sanitized *diagnostic output*, and a boolean *is cached* flag indicating whether evaluation was reused from cache.

A session's *verification evaluator* coordinates verification execution for active targets.

The verification evaluator:

- Evaluates configured verification checks for a specified target node or across all active targets in the session.

- Filters diagnostic text by stripping build system progress lines, target load banners, and elapsed timing statistics, preserving actionable diagnostic error and warning messages.

- Caches verification results alongside target file hashes, reusing cached results when target file contents have not changed since the previous evaluation.
