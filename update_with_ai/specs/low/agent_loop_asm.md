<!-- Dependencies (md files to read alongside this one):
  - agent_loop_impl.md
  - agent_loop_config.md
  - conversation_history_impl.md
  - loop_guard_impl.md
-->

# Implementation LLS: agent_loop_asm

## Data Types
```python
from agent_loop_impl import AgentLoopImpl
from agent_loop_config import AgentLoopConfig
from conversation_history_impl import ConversationHistoryImpl
from loop_guard_impl import LoopGuardImpl

class AgentLoopAsm(AgentLoopImpl):
    def __init__(self, config: AgentLoopConfig): ...
```

## Composition

- ConversationHistoryImpl
- LoopGuardImpl

## Behavioral Description

`AgentLoopAsm` fulfills the `AgentLoop` Protocol by assembling `ConversationHistoryImpl` and `LoopGuardImpl` into `AgentLoopImpl`.

- Constructs `ConversationHistoryImpl` and `LoopGuardImpl(config=config)`.
- Passes them to `AgentLoopImpl.__init__(config=config, conversation_history=..., loop_guard=...)`.
- Performs configuration and assembly only; it has no test module.

## Invariants

- Implements no functionality beyond assembly

## Non-Concerns

- **Assembly construction order:** Construction order is an implementation detail.
