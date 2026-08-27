<!-- Dependencies (md files to read alongside this one):
  - agent_loop_impl.md
-->

# Interface LLS: build_agent_config

## Data Types
```python
from dataclasses import dataclass
from typing import Optional, Protocol, TypeAlias
from agent_loop_impl import AgentLoopConfig

DEFAULT_CONFIG_TARGET = "//agent_configs:default"
CONFIG_TARGET_ENV = "AGENT_CONFIG_TARGET"
API_KEY_ENV = "AGENT_API_KEY"

ConfigTarget: TypeAlias = str

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
    session_start_reads: bool = True
    step_sections: bool = True

class BuildAgentConfig(Protocol):
    def build_agent_loop_config(self, config_target: ConfigTarget | None = None, workspace_root: Optional[str] = None) -> AgentLoopConfig: ...
```

`AgentConfig` mirrors the generated module's `AGENT_CONFIG` dict (see
`specs/high/build_agent_config.md`); `api_key_env` is the exact environment
variable holding the API key (empty means the plain `AGENT_API_KEY`
variable applies). `session_start_reads` and `step_sections` are the sandbox
gates (per `specs/high/build_agent_config.md`): whether the run's sandbox provides
session-start reads and whether step mode is enabled (both default to
enabled). All failures are unexpected failures, signaled as exceptions (see
Failure Handling below).

## Term definitions

- **agent configuration** → the `AgentConfig` type (definition in Data Types)
- **config target** → the `ConfigTarget` alias (definition in Data Types)
- **API key** → term definition: a secret credential for the language model service; an API key is never part of an agent configuration or a config target — it is provided by the caller through the environment
- **agent-loop configuration** → the `AgentLoopConfig` type from agent_loop_impl

## Component-Provided Operations

### `build_agent_loop_config`

```python
def build_agent_loop_config(self, config_target: ConfigTarget | None = None, workspace_root: Optional[str] = None) -> AgentLoopConfig
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
  - The config target label is malformed, or the generated module is not
    found in runfiles or bazel-bin; the failure message includes the
    `bazel build` command for the config target.
  - The config's pinned API-key environment variable is unset (when one is
    named), or `AGENT_API_KEY` is unset (when none is named); the failure
    message names the exact variables.

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
- **Identity fields:** `AgentConfig.label` and `AgentConfig.name` carry the
  config target's label and rule name for attribution — a pin beyond the
  HLS's term enumeration of the config's contents (the generated `{name}_config.py`
  module convention names the rule), recorded here so they are not read as
  invented configuration.
