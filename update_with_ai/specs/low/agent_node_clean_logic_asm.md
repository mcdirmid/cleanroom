<!-- Dependencies (md files to read alongside this one):
  - agent_node_clean_logic_impl.md
  - agent_loop_impl.md
  - build_agent_config_impl.md
  - sandbox_asm.md
  - dag_clean_logic.md
  - build_graph_storage.md
  - build_agent_config.md
  - agent_loop.md
-->

# Implementation LLS: agent_node_clean_logic_asm

## Data Types
```python
from typing import Optional
from agent_node_clean_logic_impl import AgentNodeCleanLogicImpl
from build_graph_storage import BuildGraphStorage
from build_agent_config import ConfigTarget
from agent_loop import LoggerCallback

class AgentNodeCleanLogicAsm(AgentNodeCleanLogicImpl):
    def __init__(self, graph: BuildGraphStorage, workspace_root: str, config_target: Optional[ConfigTarget] = None, logger: Optional[LoggerCallback] = None) -> None: ...
```

Subclasses `AgentNodeCleanLogicImpl` with pre-wired agent loop, configuration loader, and sandbox factory via `SandboxAsm`. Fulfills the `DagCleanLogic` protocol via `AgentNodeCleanLogicImpl`. This assembly performs configuration and assembly only and is never tested.

## Composition

- BuildAgentConfigImpl (agent configuration loading)
- AgentLoopImpl (agent loop)
- SandboxAsm (sandbox assembly)
- AgentNodeCleanLogicImpl (agent clean logic)

## Behavioral Description

- Assembles the concrete agent clean logic at construction: uses `BuildAgentConfigImpl` to resolve the config target (argument, then `AGENT_CONFIG_TARGET`, then `//agent_configs:default`), load the agent configuration, and resolve the API key from the environment.
- Constructs `AgentLoopImpl` with the resolved configuration.
- Supplies a sandbox factory that delegates to `SandboxAsm`, gating session-start reads and step sections according to the agent configuration.
- Passes the graph, agent loop config, sandbox factory, agent loop factory, and optional logger callback to `super().__init__`.
- Inherits and implements the `DagCleanLogic` protocol through `AgentNodeCleanLogicImpl`.
- No functionality beyond configuration and assembly is performed; this assembly is never tested.

## Invariants

- The concrete implementations are selected here, at construction; operations never select components.
- No persistent state is held across calls: each instance is a fresh clean logic component.

## Non-Concerns

- **Consumption:** how the assembled clean logic is used is unspecified here.
- **Selection policy:** the concrete implementations wired here are a default assembly; other selections may differ.
