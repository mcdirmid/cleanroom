<!-- Dependencies (md files to read alongside this one):
  - bazel_agent_config-high.md
  - agent_loop-low.md
-->

# Interface LLS: bazel_agent_config

## Data Types

```python
from dataclasses import dataclass
from typing import Optional, Protocol
from agent_loop import AgentLoopConfig

DEFAULT_CONFIG_TARGET = "//agent_configs:default"
CONFIG_TARGET_ENV = "AGENT_CONFIG_TARGET"
API_KEY_ENV = "AGENT_API_KEY"

@dataclass
class AgentConfig:
    label: str
    name: str
    model: str
    base_url: str
    api_key_env: str
    max_iterations: int
    temperature: float
    timeout: float
    max_tokens: Optional[int]

class ConfigNotFoundError(ValueError): ...
class ApiKeyNotFoundError(ValueError): ...
```

`AgentConfig` mirrors the generated module's `AGENT_CONFIG` dict (see
`bazel_agent_config-high.md`); `api_key_env` is the exact environment
variable holding the API key (empty means the plain `AGENT_API_KEY`
variable applies). The two exception types signal unexpected failures (see
Failure Handling below).

```python
class BazelAgentConfig(Protocol):
    def build_agent_loop_config(self, config_target: Optional[str] = None, workspace_root: Optional[str] = None) -> AgentLoopConfig: ...
```

## Component-Provided Operations

### `build_agent_loop_config`

```python
def build_agent_loop_config(self, config_target: Optional[str] = None, workspace_root: Optional[str] = None) -> AgentLoopConfig
```

**Purpose:** Provide the agent-loop configuration for an agent_config target,
combining the selected agent configuration with the API key resolved from
the environment.

**Preconditions:**
- `config_target`, when provided, is a canonical main-repo Bazel label for an
  agent_config target
- The config target's generated module is available in runfiles or in
  bazel-bin under the workspace root
- The environment provides an API key for the configuration's environment
  label

**Postconditions:**
- Provides an `AgentLoopConfig` whose parameters match the selected agent
  configuration exactly, with the API key from the environment.
- Config-target selection: explicit `config_target`, then
  `AGENT_CONFIG_TARGET`, then `//agent_configs:default`.
- API-key resolution: the config's pinned API-key environment variable
  (`api_key_env`) when one is named — that variable alone, with no fallback —
  otherwise the plain `AGENT_API_KEY` variable.

**Failure Handling:**
- All failures are unexpected failures (exceptions):
  - `ConfigNotFoundError` — the config target label is malformed, or the
    generated module is not found in runfiles or bazel-bin; the message
    includes the `bazel build` command for the config target.
  - `ApiKeyNotFoundError` — the config's pinned API-key environment variable
    is unset (when one is named), or `AGENT_API_KEY` is unset (when none is
    named); the message names the exact variables.

**HLS Justification:** "Provides an agent-loop configuration whose parameters
match the selected agent configuration exactly, with the API key resolved
from the environment."

## Invariants

- An `AgentConfig` never contains an API key.
- Configuration values from the generated module pass through unchanged.
- No persistent state is held across calls.

## Non-Concerns

- Where config targets are declared (which Bazel package): the convention is
  agent_configs/BUILD.bazel.
- The format of the generated module file: produced by the `agent_config`
  rule (update_with_ai/agent_config.bzl), not specified here.
- The meaning of individual configuration parameters: they pass through
  unchanged.
