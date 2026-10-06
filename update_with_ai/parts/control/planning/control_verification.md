# control_verification interface component

imports: agent_session, agent_node_config, dag_storage

## Intent

The control_verification interface component defines contracts for evaluating verification checks, filtering build diagnostic noise, and caching evaluation results against file hashes.

In iterative agent coding workflows, build and test executions produce verbose output containing compilation banners, elapsed timings, and progress lines. These outputs consume context window tokens without providing actionable debugging value. The control_verification component isolates diagnostic messages, standardizes verification outcome reporting, and prevents redundant check executions by memoizing results against source file hashes.

## Factored Contracts

### Typing

- A verification result records a passed status, diagnostic output, and a cached evaluation indicator.
- A verification evaluator operates within the agent session lifecycle tier.

### Contracts

- A verification evaluator evaluates configured verification checks for a specified target node. [evaluate_target_checks]
- A verification evaluator evaluates verification checks across all open session targets. [evaluate_all_checks]
- A verification evaluator strips build system progress indicators from diagnostic text. [filter_progress_noise]
- A verification evaluator strips target load banners from diagnostic text. [filter_banner_noise]
- A verification evaluator strips elapsed timing statistics from diagnostic text. [filter_timing_noise]
- A verification evaluator memoizes verification results keyed by target file hashes. [cache_result_by_hash]
- A verification evaluator reuses memoized results when target file hashes are unchanged. [reuse_cached_result]

### Woven Contracts

- When evaluating checks for a target whose files have not changed since prior evaluation, the verification evaluator returns the memoized verification result with the cached flag set. [cache_result_by_hash, reuse_cached_result]
- When check execution produces diagnostic output, the verification evaluator sanitizes the output by removing build progress lines, load banners, and elapsed timing statistics before reporting the outcome. [filter_progress_noise, filter_banner_noise, filter_timing_noise]

## Grounding

### Knowledge Provisions

- Evaluates target verification checks with terminal noise filtering. [verification_evaluation]
- Memoizes check results by file hash to avoid redundant subprocess execution. [verification_caching]

### Knowledge Requirements

- Resolution of configured verification check commands for target nodes.
  - Deferred: Resolved from agent_node_config in implementation.
- Computation of cryptographic hashes of target read-write files.
  - Deferred: Computed via SHA-256 in implementation.
- Subprocess execution of verification commands.
  - Deferred: Delegated to subprocess execution in implementation.
