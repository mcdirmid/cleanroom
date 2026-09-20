# Requirements specified in sandbox.pyi
from typing import List, Protocol
from dataclasses import dataclass
from . import tool_provider


@dataclass(frozen=True)
class StartupToolExecution:
    tool_name: str
    wire_parameter_bindings: tool_provider.WireParameterBindings
    response: tool_provider.Response


class Sandbox(Protocol):
    @property
    def has_modifications(self) -> bool: ...

    def get_startup_tool_executions(self) -> List[StartupToolExecution]: ...

    def materialize_startup_templates(self) -> None: ...
