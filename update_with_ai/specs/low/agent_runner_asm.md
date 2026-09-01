<!-- Dependencies (md files to read alongside this one):
  - openai_ext.md
  - loop_guard_impl.md
  - runner_logger_impl.md
  - agent_runner_impl.md
  - agent_runner.md
-->

# Implementation LLS: agent_runner_asm

## Data Types
```python
from typing import Optional
from openai_ext import ModelName
from agent_runner_impl import AgentRunnerImpl
from loop_guard_impl import LoopGuardImpl
from runner_logger_impl import RunnerLoggerImpl

class AgentRunnerAsm(AgentRunnerImpl):
    def __init__(
        self,
        model: ModelName,
        base_url: str = "https://api.openai.com/v1",
        api_key_env_var: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> None: ...
```

- `AgentRunnerAsm` → corresponds to *agent runner*: assembles an *agent runner* by wiring runner logging and loop guard implementations.

## Composition

- LoopGuardImpl
- RunnerLoggerImpl
- AgentRunnerImpl

## Behavioral Description

- `AgentRunnerAsm` instantiates `LoopGuardImpl`, `RunnerLoggerImpl`, and `OpenAiExtImpl` (configured with `base_url`, `timeout_seconds`, and API key resolved from `api_key_env_var` or the process environment) directly within `__init__` before delegating to `super().__init__(openai_ext=ext, model=model)`.
- Executes iterative agent turns with loop repetition prevention and execution logging.

## Invariants

- Implements no functionality beyond assembly.
