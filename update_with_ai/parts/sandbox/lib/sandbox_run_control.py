from typing import Protocol, Sequence, Set, Tuple
from . import tool_provider
from update_with_ai.parts.agent.lib import agent_file_alias, agent_node_config

class RunController(Protocol):
    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        ...

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        ...

class AdvanceTool(tool_provider.Tool, Protocol):
    pass

class FinishTool(tool_provider.Tool, Protocol):
    @property
    def change_summary(self) -> tool_provider.Parameter:
        ...

class FailTool(tool_provider.Tool, Protocol):
    pass

class BlameTool(tool_provider.Tool, Protocol):
    pass

class RunTestsTool(tool_provider.Tool, Protocol):
    pass

