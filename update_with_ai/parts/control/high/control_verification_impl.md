<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 61d6c9deaf86
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

The verification evaluator implements verification check evaluation for the session.

When evaluating verification checks:

- The verification evaluator retrieves verification checks configured on the target node or configured globally for the active session from node config.

- When target read-write file hashes match the cached file hash recorded from the previous evaluation, the verification evaluator reuses the cached verification result, setting the is cached flag to true without invoking check subprocesses.

- When evaluating verification checks for a target whose files have changed or which has not yet been evaluated, the verification evaluator executes each configured check command sequentially.

- If any verification check exits with a non-zero exit code or writes failure diagnostics, the verification evaluator marks the verification result as failing, captures the error output, strips compiler diagnostic noise lines starting with build progress indicators or load banners, and stores the failing outcome in the file hash cache.

- If all verification checks complete with exit code zero, the verification evaluator marks the verification result as passed, captures any standard output, strips compiler diagnostic noise, and caches the passing outcome alongside the current file hashes.
