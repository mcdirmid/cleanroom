# bazel_agent_config_impl

fulfills: bazel_agent_config
imports: bazel_agent_config (contract), agent_loop (agent-loop configuration)
terms (from bazel_agent_config): agent configuration, config target, API key
terms (refined): config target -> a Bazel agent_config target in the main repository

## Deltas beyond the bazel_agent_config contract

### Behavior

- Implements the contract by locating the generated module for the config target in the runfiles tree first, then bazel-bin under the workspace root, importing it, and combining it with the environment-resolved API key.
- Config-target selection follows the interface contract: explicit argument, then the AGENT_CONFIG_TARGET environment variable, then //agent_configs:default.
- API-key resolution follows the interface contract: the config's pinned API-key environment variable when one is named (that variable alone, with no fallback), otherwise the plain AGENT_API_KEY variable.
- The generated module is imported via the importlib machinery from a path derived from the config target label; keys in the generated dict that are not AgentConfig fields are dropped.

### Refined terms

- Config target: a Bazel agent_config target in the main repository whose generated module ({name}_config.py) is bundled into the runfiles of the generated *_clean binaries via //agent_configs:all_configs, or built separately and found under bazel-bin.

### Operation Boundaries

- Every call operates on per-call inputs; no state persists across calls.
- The API key is read from the process environment per call.

### Error Handling

- All failures are unexpected failures per the interface contract: ConfigNotFoundError for a malformed label or a missing generated module (with guidance to build the config target), ApiKeyNotFoundError when no API key is available — the pinned API-key environment variable unset (when one is named), or AGENT_API_KEY unset.

## Non-concerns

- The format of the generated module: produced by the `agent_config` rule (update_with_ai/agent_config.bzl).
- Which environment variables a caller sets: only the resolution order and the variable names are specified.
