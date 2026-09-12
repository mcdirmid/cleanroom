from typing import List, Protocol
from framework import data_type, operation, singleton_type
from dataclasses import dataclass
import model_config
import tool_provider

@dataclass(frozen=True)
@data_type
class StartupToolExecution:
    """
PURPOSE:
Paired tool request and response for an initial tool invocation at session start
"""

    def __init__(self, tool_name: str, wire_parameter_bindings: tool_provider.WireParameterBindings, response: tool_provider.Response) -> None:
        ...

    @property
    def tool_name(self) -> str:
        """
PURPOSE:
Name of the tool invoked for the startup execution
"""
        ...

    @property
    def wire_parameter_bindings(self) -> tool_provider.WireParameterBindings:
        """
PURPOSE:
Wire parameter bindings supplied to the tool for the startup execution
"""
        ...

    @property
    def response(self) -> tool_provider.Response:
        """
PURPOSE:
Response produced by executing the tool for the startup execution
"""
        ...

@singleton_type('agent_session')
class Sandbox(Protocol):
    """
PURPOSE:
Defined as an agent session service coordinating startup context and file management

FRESH_REQUIREMENTS:
- The sandbox exposes whether workspace file modifications occurred during the session.
"""

    @property
    def has_modifications(self) -> bool:
        """
PURPOSE:
Exposes whether workspace file modifications occurred during the session
"""
        ...

    @operation
    def get_startup_tool_executions(self) -> List[StartupToolExecution]:
        """
PURPOSE:
Retrieves startup tool executions based on active configuration

FRESH_REQUIREMENTS:
- The sandbox exposes startup tool executions as an ordered sequence of initial tool executions based on active configuration.
"""
        ...

    @operation
    def materialize_startup_templates(self) -> None:
        """
PURPOSE:
Materializes starter templates into missing read-write files at session start

FRESH_REQUIREMENTS:
- Materializing startup templates populates missing read-write files without overwriting existing files.
"""
        ...
