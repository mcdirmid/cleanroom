# bazel_agent_config_impl

fulfills: bazel_agent_config
imports: bazel_agent_config (contract), agent_loop (agent-loop configuration)
terms (from bazel_agent_config): agent configuration, config target, API key
terms (refined): config target

## Deltas

- Implements the contract by locating the generated module for the config target in the runfiles tree first, then bazel-bin under the workspace root, importing it, and combining it with the environment-resolved API key.
- Config-target selection follows the interface contract; the selecting environment variable is AGENT_CONFIG_TARGET.
- The generated module is imported via the importlib machinery from a path derived from the config target label; keys in the generated dict that are not AgentConfig fields are dropped.
- [state] Every call operates on per-call inputs; no state persists across calls.
- [external] The API key is read from the process environment per call.
- [refines] config target -> a Bazel agent_config target in the main repository whose generated module ({name}_config.py) is bundled into the runfiles of the generated *_clean binaries via //agent_configs:all_configs, or built separately and found under bazel-bin.

## Non-concerns

- The format of the generated module: produced by the `agent_config` rule (update_with_ai/agent_config.bzl).
- Which environment variables a caller sets: only the resolution order and the variable names are specified.
