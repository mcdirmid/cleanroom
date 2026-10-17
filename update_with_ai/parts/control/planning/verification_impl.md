<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: b265a489eb67
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# verification_impl implementation component

## Intent

The verification_impl implementation component provides concrete mechanics for subprocess invocation of verification commands, regex-based diagnostic noise scrubbing, and SHA-256 file hash tracking.

Compilers and build tools output varied terminal sequences and progress indicators. The implementation cleans lines matching known compiler noise prefixes, computes SHA-256 hashes of target source files, executes checks sequentially until failure or completion, and records outcomes in an in-memory hash cache.

## Factored Contracts

### Contracts

- The verification evaluator queries node configuration for verification checks associated with the target. [resolve_target_checks]
- The verification evaluator computes the current hash of target read-write files. [compute_file_hash]
- The verification evaluator matches current file hashes against the cache to detect changes. [detect_hash_match]
- The verification evaluator executes each configured check command via subprocess execution. [execute_check_command]
- The verification evaluator marks the result as failed when a check process exits non-zero. [record_check_failure]
- The verification evaluator marks the result as passed when all check processes exit zero. [record_check_success]
- The verification evaluator cleans stdout and stderr lines matching build noise prefixes. [clean_diagnostic_lines]
- The verification evaluator writes the final result and hash entry to the cache. [update_hash_cache]

### Woven Contracts

- When current file hashes match the cached hash, the evaluator skips command execution and returns the cached outcome with is_cached true. [detect_hash_match, verification: [reuse_cached_result]]
- When a check command fails, the evaluator stops subsequent checks, cleans error text of noise prefixes, marks the result as failing, and updates the cache. [execute_check_command, record_check_failure, clean_diagnostic_lines, update_hash_cache]
- When all check commands succeed, the evaluator cleans standard output of noise prefixes, marks the result as passing, and updates the cache. [execute_check_command, record_check_success, clean_diagnostic_lines, update_hash_cache]

## Grounding

### Knowledge Provisions

- Evaluates target verification checks with terminal noise filtering. [verification_evaluation]
- Memoizes check results by file hash to avoid redundant subprocess execution. [verification_caching]

### Inherited Deferred Requirements

- Resolution of configured verification check commands for target nodes.
  - Grounded: [node_config: [node_configuration_service]]
- Computation of cryptographic hashes of target read-write files.
  - Grounded: [file_alias: [alias_mapping], verification_caching]
- Subprocess execution of verification commands.
  - Grounded: [verification_evaluation]

### Knowledge Requirements

- Regex-based diagnostic noise scrubbing of progress bars, build banners, and timing stats.
  - Grounded: [verification_evaluation]
