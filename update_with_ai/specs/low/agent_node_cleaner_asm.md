<!-- Dependencies (md files to read alongside this one):
  - build_graph_storage.md
  - build_agent_config_impl.md
  - build_agent_config.md
  - agent_runner_asm.md
  - sandbox_asm.md
  - conversation_history_impl.md
  - agent_node_cleaner_impl.md
  - runner_logger.md
  - agent_node_cleaner.md
-->

# Implementation LLS: agent_node_cleaner_asm

## Data Types
```python
from typing import Optional
from build_graph_storage import BuildGraphStorage
from agent_node_cleaner_impl import AgentNodeCleanerImpl
from build_agent_config_impl import BuildAgentConfigResolverImpl
from agent_runner_asm import AgentRunnerAsm
from sandbox_asm import SandboxAsm
from conversation_history_impl import ConversationHistoryFactoryImpl
from runner_logger import RunnerLogger
from build_agent_config import ConfigTarget

class AgentNodeCleanerAsm(AgentNodeCleanerImpl):
    def __init__(
        self,
        config_target: Optional[ConfigTarget] = None,
        storage: Optional[BuildGraphStorage] = None,
        logger: Optional[RunnerLogger] = None,
    ) -> None: ...
```

- `AgentNodeCleanerAsm` → corresponds to *agent node cleaner*: assembles an *agent node cleaner* by wiring the agent runner assembly, sandbox assembly, conversation history factory, and build agent configuration resolver.

## Composition

- BuildAgentConfigResolverImpl
- AgentRunnerAsm
- SandboxAsm
- ConversationHistoryFactoryImpl
- AgentNodeCleanerImpl

## Behavioral Description

- `AgentNodeCleanerAsm` instantiates `BuildAgentConfigResolverImpl`, resolves declarative agent configuration, and passes model, base URL, API key environment variable, and timeout settings to `AgentRunnerAsm` directly within `__init__`.
- Constructs `SandboxAsm` and `ConversationHistoryFactoryImpl`.
- Delegates to `super().__init__(runner=runner, sandbox_factory=sandbox_factory, conversation_history_factory=conversation_history_factory, storage=storage)`.

## Invariants

- Implements no functionality beyond assembly.
- Concrete implementation classes are instantiated internally and never passed as constructor arguments.
