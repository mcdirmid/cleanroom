<!-- Dependencies (md files to read alongside this one):
  - bazel_agent_config-low.md
  - agent_loop_impl-low.md
-->

# Implementation LLS: bazel_agent_config_impl

## Data Types
```python
from bazel_agent_config import AgentConfig, BazelAgentConfig
from agent_loop_impl import AgentLoopConfig

class BazelAgentConfigImpl(BazelAgentConfig): ...

class ConfigNotFoundError(Exception): ...

class ApiKeyNotFoundError(Exception): ...
```

`BazelAgentConfigImpl` implements the `BazelAgentConfig` Protocol (see
`bazel_agent_config` Interface LLS). Constructed with no configuration: the
config target and workspace root are per-call parameters of the class methods.

## Behavioral Description

- `parse_target` splits a canonical label into (package path, target name):
  `//pkg:name` -> `("pkg", "name")` and `//pkg` -> `("pkg", "pkg")`; invalid
  labels (non-canonical or repository-qualified) signal `ConfigNotFoundError`.
- `find_config_file` locates the generated module for a config target:
  runfiles candidates (`RUNFILES_DIR` / `BAZEL_RUNFILES`, with and without
  the `_main` repo prefix) first, then bazel-bin under the workspace root
  (explicit `workspace_root`, then `BUILD_WORKSPACE_DIRECTORY`, then the
  current working directory); a missing module signals `ConfigNotFoundError`
  with the `bazel build` command for the config target.
- `load_config` imports the generated module (via importlib) and constructs
  an `AgentConfig` from its `AGENT_CONFIG` dict, dropping keys that are not
  `AgentConfig` fields.
- `resolve_api_key(api_key_env)` reads the pinned API-key environment
  variable when one is named (that variable alone, with no fallback);
  otherwise it reads the plain `AGENT_API_KEY` variable; absence signals
  `ApiKeyNotFoundError` naming the exact variables.
- `resolve_config_target` selects the config target: explicit argument, then
  the `AGENT_CONFIG_TARGET` environment variable, then `//agent_configs:default`.
- `build_agent_loop_config` combines the three: selects the config target,
  loads its agent configuration, resolves the API key (the pinned variable
  or `AGENT_API_KEY`), and provides an `AgentLoopConfig`.
- `AgentConfig.to_agent_loop_config` threads the agent-loop parameters (model,
  base URL, iteration limit, temperature, timeout, and token limit) through to
  the `AgentLoopConfig`, inserting the resolved API key; the sandbox gates
  (`session_start_reads`, `step_sections`) are not part of the agent-loop
  configuration (see `bazel_runner_impl`).

**HLS Justification:** The interface specifies config-target selection,
API-key resolution, and module location; the implementation provides those
operations.

## Invariants

- Every call operates on per-call inputs; no state persists across calls.
- The API key is read from the process environment per call.

## Non-Concerns

- The format of the generated module file: produced by the `agent_config`
  rule (update_with_ai/agent_config.bzl), not specified here.
- Which environment variables a caller sets: only the resolution order and
  the variable names are specified.
