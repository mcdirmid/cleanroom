from typing import Protocol, Sequence, Set, Tuple
from . import file_alias, node_config, tool_provider

VerificationCheck = node_config.VerificationCheck

class RunController(Protocol):
    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
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

