<!-- Dependencies (md files to read alongside this one):
  - bazel_agent_config-low.md
-->

# Implementation LLS: bazel_agent_config_impl

## Data Types

```python
from bazel_agent_config import AgentConfig, ConfigNotFoundError, ApiKeyNotFoundError
from agent_loop import AgentLoopConfig

class BazelAgentConfigImpl(BazelAgentConfig): ...
```

`BazelAgentConfigImpl` implements the `BazelAgentConfig` Protocol (see
`bazel_agent_config` Interface LLS).

## Config

None — the implementation bundles no imported capabilities; the config target
and workspace root are per-call parameters of the class methods (see
`bazel_agent_config` Interface LLS).

**HLS Justification:** The interface specifies a config target and workspace
root per call; the implementation imports no configuration.

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
- `AgentConfig.to_agent_loop_config` threads every parameter through to the
  `AgentLoopConfig`, inserting the resolved API key.

**HLS Justification:** The interface specifies config-target selection,
API-key resolution, and module location; the implementation provides those
operations.

## Invariants

- An `AgentConfig` never contains an API key.
- Configuration values from the generated module pass through unchanged (no
  transformation of model, limits, or URLs).
- No persistent state is held across calls.

## Non-Concerns

- The format of the generated module file: produced by the `agent_config`
  rule (update_with_ai/agent_config.bzl), not specified here.
- Which environment variables a caller sets: only the resolution order and
  the variable names are specified.
