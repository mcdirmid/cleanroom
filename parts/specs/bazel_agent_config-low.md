<!-- Dependencies (md files to read alongside this one):
  - agent_loop-low.md
-->

# Interface LLS: bazel_agent_config

## Data Types
```python
from typing import Protocol, TypeAlias
from dataclasses import dataclass

ConfigTarget: TypeAlias = str
ApiCredential: TypeAlias = str

@dataclass
class AgentConfig:
    model_identifier: str
    base_url: str
    iteration_limit: int
    temperature: float
    timeout: int
    token_limit: int
    session_start_enabled: bool
    step_mode_enabled: bool
    api_key_env_var: str | None

@dataclass
class AgentLoopConfig:
    agent_config: AgentConfig
    api_key: ApiCredential

class BazelAgentConfig(Protocol):
    def resolve(self, config_target: ConfigTarget | None = None,
                workspace_root: str | None = None) -> AgentLoopConfig: ...
```

**ConfigTarget:** A canonical main-repo Bazel label in the form `//pkg:name` identifying an agent_config target whose generated module holds the agent configuration.

**ApiCredential:** A secret credential for the language model service, provided by the caller through the environment.

**AgentConfig:** The full set of agent/model parameters — model identifier, base URL, iteration limit, temperature, timeout, and token limit — and the sandbox gates — whether session-start reads are enabled and whether step mode is enabled — excluding the API key. An agent configuration may name the exact environment variable holding its API key (an API-key environment variable) and is identified by a config target.

**AgentLoopConfig:** The complete agent-loop configuration combining an agent configuration with a resolved API key.

## Term definitions

- **agent configuration** → the `AgentConfig` alias
- **config target** → the `ConfigTarget` alias
- **API key** → the `ApiCredential` alias

## Component-Provided Operations

### `resolve`

```python
def resolve(self, config_target: ConfigTarget | None = None,
            workspace_root: str | None = None) -> AgentLoopConfig: ...
```

**Purpose:** Resolve the complete agent-loop configuration by loading the agent configuration from a config target (or the default config target) and combining it with an API key resolved from the environment.

**Preconditions:** The config target, when provided, is a canonical main-repo Bazel label. The config target's generated module exists in the runfiles tree or in bazel-bin under the workspace root. The environment provides an API key for the configuration: the pinned variable (when one is named by the agent configuration) or AGENT_API_KEY.

**Postconditions:** Returns an `AgentLoopConfig` whose parameters match the selected agent configuration exactly, with the API key resolved from the environment. Selection priority: explicit config target wins; otherwise an environment variable selects the config target; otherwise the default config target `//agent_configs:default` applies. When an agent configuration names an API-key environment variable, that variable alone supplies the API key; `AGENT_API_KEY` does not apply. When it names none, the plain `AGENT_API_KEY` variable supplies the key. No API key is part of the agent configuration or config target.

**Failure Handling:** Unexpected failures only:
- Config target's generated module missing: the config target is invalid or was not built, signaled with guidance to build it.
- API key missing: the pinned API-key environment variable is unset (when the configuration names one), or `AGENT_API_KEY` is unset (when it does not), signaled with the exact variable names.
- Config target label malformed: not a canonical main-repo label.

**HLS Justification:** Contract → Operations → "Select an agent configuration"; Contract → Guarantees → all guarantee statements; Contract → Unexpected failures.

## Invariants

- Each resolve call is independent; no state persists across calls.

## Non-Concerns

- **Where config targets are declared (which Bazel package):** any package may declare agent_config targets; the convention is `agent_configs/BUILD.bazel`. — Bounded by the HLS non-concern; the component does not constrain where targets are declared.
- **How agent configurations are stored on disk (generated module format):** the generated module and JSON forms are implementation-specific. — Bounded by the HLS non-concern; the component treats the generated module as an opaque importable module.
- **The meaning of individual parameters (temperature, timeout, token limit):** those parameters pass through unchanged to the agent-loop configuration. — Bounded by the HLS non-concern; the component does not interpret or validate parameter semantics.
Read 55 lines (line-numbered)
