<!-- Dependencies (md files to read alongside this one):
  - agent_runner.md
-->

# Interface LLS: build_agent_config

## Data Types
```python
from typing import Protocol, TypeAlias, Optional
from dataclasses import dataclass
from agent_runner import IterationLimit

ConfigTarget: TypeAlias = str
ModelIdentifier: TypeAlias = str
ServiceBaseUrl: TypeAlias = str
EnvVarName: TypeAlias = str

@dataclass(frozen=True)
class AgentConfig:
    model: ModelIdentifier
    base_url: ServiceBaseUrl
    iteration_limit: IterationLimit
    temperature: float = 0.0
    timeout_seconds: int = 60
    api_key_env_var: Optional[EnvVarName] = None

class BuildAgentConfigResolver(Protocol):
    def resolve_config(self, target: Optional[ConfigTarget] = None) -> AgentConfig: ...
```

- `ConfigTarget` → corresponds to *config target*: an identifier selecting an *agent configuration*.
- `ModelIdentifier` → corresponds to model identifier string.
- `ServiceBaseUrl` → corresponds to service base URL string.
- `EnvVarName` → corresponds to environment variable name string.
- `AgentConfig` → corresponds to *agent configuration*: a set of model parameters, authentication environment variables, timeouts, and *iteration limits* for an agent run.
- `BuildAgentConfigResolver` → corresponds to *build agent config resolver*: a resolver that resolves an *agent configuration* from a *config target*.

## Term definitions

- **config target** → the `ConfigTarget` alias
- **agent configuration** → the `AgentConfig` alias
- **build agent config resolver** → term definition: a resolver that resolves an *agent configuration* from a *config target*.

## Component-Provided Operations

### `resolve_config`

```python
def resolve_config(self, target: Optional[ConfigTarget] = None) -> AgentConfig: ...
```

**Purpose:** (BuildAgentConfigResolver) Resolves declarative agent configurations from workspace targets and binds credentials from the process environment.

**Preconditions:** None.

**Postconditions:**
- Returns the resolved `AgentConfig` matching the target or workspace defaults.

**Failure Handling:** Always succeeds when target or defaults are configured.

**HLS Justification:** "Resolving an *agent configuration* binds authentication credentials from the process environment."

## Invariants

- API keys are resolved at runtime from process environment variables.
