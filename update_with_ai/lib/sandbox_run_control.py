from typing import Protocol, Sequence, Set, Tuple
from . import file_alias
from . import tool_provider

class VerificationCheck(Protocol):
    def verify(self) -> Tuple[bool, str]:
        ...

class RunController(Protocol):
    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        ...

class AdvanceTool(tool_provider.Tool, Protocol):
    pass

class FailTool(tool_provider.Tool, Protocol):
    pass

class BlameTool(tool_provider.Tool, Protocol):
    pass
