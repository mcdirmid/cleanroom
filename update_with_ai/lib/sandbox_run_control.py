from typing import Protocol, Set, Tuple
from . import file_alias
from . import tool_provider

class VerificationCheck(Protocol):
    def verify(self) -> Tuple[bool, str]:
        ...

class RunController(Protocol):
    @property
    def verification_checks(self) -> Set[VerificationCheck]:
        ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        ...

    def install_verification_check(self, check: VerificationCheck) -> None:
        ...

class AdvanceTool(tool_provider.Tool, Protocol):
    pass

class FailTool(tool_provider.Tool, Protocol):
    pass

class BlameTool(tool_provider.Tool, Protocol):
    pass
