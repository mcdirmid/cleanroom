<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T04:08:58Z
CHANGE: Removed the unused agent_node_config import and its delegation clause: verification check definitions are grounded in the low-level specification without an agent_node_config member, so the interface now declares only agent_session and dag_storage.
CODE_HASH: 9b07771f7e18
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# control_verification interface component

imports: agent_session, dag_storage

## Purpose

The control_verification interface component defines verification check evaluation, compiler diagnostic noise filtering, and verification outcome caching across workspace targets.

Autonomous coding tasks and validation processes require dependable feedback loops to verify that generated code compiles, type-checks, and passes test suites before committing changes. Without standardized verification evaluation, raw compiler outputs flood the agent context with noisy build banners, while redundant re-executions of unchanged files waste compute. The control_verification interface component provides verification assessment over one target or every active target, sanitizes diagnostic output, and caches evaluation results against file hashes.

**Out of scope:** The control_verification interface component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

**Delegated:** Node status is delegated to dag_storage; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *verification result* reports whether verification checks succeeded or failed, carrying a *passed* status, sanitized *diagnostic output*, and a *reuse* status indicating whether evaluation was reused from cache.

An agent session's *verification evaluator* coordinates verification execution for active targets.

The verification evaluator evaluates the configured verification checks of a specified target node, or of every active target in the session.

The verification evaluator filters diagnostic text by stripping build system progress lines, target load banners, and elapsed timing statistics, preserving actionable diagnostic error and warning messages.

The verification evaluator caches verification results alongside target file hashes, reusing a cached result while target file contents are unchanged since the previous evaluation.
