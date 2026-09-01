<!-- Dependencies (md files to read alongside this one):
  - agent_runner.md
  - build_agent_config.md
-->

# Implementation LLS: build_agent_config_impl

## Data Types
```python
from build_agent_config import BuildAgentConfigResolver

class BuildAgentConfigResolverImpl(BuildAgentConfigResolver):
    def __init__(self) -> None: ...
```

## Behavioral Description

- Resolves model parameters and iteration limits from target definitions or system defaults.
- Binds API credentials dynamically from process environment variables (`OPENAI_API_KEY`, `GEMINI_API_KEY`).

## Invariants

- API keys are never hardcoded in configuration files.
