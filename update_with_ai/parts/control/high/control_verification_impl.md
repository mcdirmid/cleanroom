<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 6b4f52f74a91
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# control_verification_impl implementation component

imports: agent_session, agent_node_config, dag_storage, agent_file_alias
implements: control_verification

## Purpose

The control_verification_impl implementation component realizes subprocess execution of verification checks, compiler noise scrubbing, and source hash caching for target nodes.

Subprocess execution of compilers, type checkers, and test runners generates verbose diagnostic streams that include execution timings, analysis statistics, and cache lookup notices that consume context window space. The control_verification_impl implementation component strips non-actionable compiler noise patterns, invokes check commands defined in node configurations, and hashes primary source files to avoid redundant subprocess invocations on unchanged targets.

**Out of scope:** The control_verification_impl implementation component does not determine topological execution schedules or mutate DAG node statuses; these are handled by other components.

**Delegated:** File alias mapping and path resolution concerns are delegated to agent_file_alias.

## Types and Behavior

The verification evaluator implements verification check evaluation for an agent session.

When evaluating verification checks:

- The verification evaluator retrieves the verification checks configured on the target node or configured globally for the active session.

- The verification evaluator reuses the cached verification result and reports it as reused, without invoking check subprocesses, while target read-write file hashes match the file hash recorded from the previous evaluation.

- The verification evaluator executes each configured check command sequentially when evaluating a target whose files have changed or that has not yet been evaluated.

- The verification evaluator marks the verification result as failing when any verification check exits with a non-zero exit code or writes failure diagnostics, capturing the error output, stripping compiler diagnostic noise lines that begin with build progress indicators or load banners, and storing the failing outcome in the file hash cache.

- The verification evaluator marks the verification result as passed when every verification check completes with exit code zero, capturing any standard output, stripping compiler diagnostic noise, and caching the passing outcome alongside the current file hashes.
