from typing import Protocol, Sequence, Set, Tuple
from framework import operation, override, poly_type, singleton_type
import dag_storage
import file_alias
import sandbox_file_editor
import sandbox_guide_delivery
import tool_provider

@poly_type
class VerificationCheck(Protocol):
    """
PURPOSE:
Polymorphic service that validates session criteria
"""

    @operation
    def verify(self) -> Tuple[bool, str]:
        """
PURPOSE:
Validates session criteria, returning whether verification passed and diagnostic feedback
"""
        ...

@singleton_type('agent_session')
class RunController(Protocol):
    """
PURPOSE:
Defined as an agent session service that installs run control tools and exposes verification checks

FRESH_REQUIREMENTS:
- The run controller exposes verification checks that validate session criteria.
- The run controller caches verification evaluation results alongside the edit manager file update revision, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.
- The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
- The run controller installs a finish tool that concludes the session upon passing verification and enforces change documentation.
- The run controller installs a fail tool that terminates the run in failure.
- The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
- The run controller installs a blame tool when blame targets are configured, attributing task failure to an upstream dependency node.
"""

    @property
    def verification_checks(self) -> Sequence[VerificationCheck]:
        """
PURPOSE:
Verification checks configured for the session
"""
        ...

    @property
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Upstream bound files that can be attributed when prerequisite defects occur
"""
        ...

@singleton_type('agent_session')
class AdvanceTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that coordinates step progression through guide delivery when guide step mode is active

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...

@singleton_type('agent_session')
class FinishTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that concludes the session and enforces change documentation

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def change_summary(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter describing workspace file modifications
"""
        ...

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...

@singleton_type('agent_session')
class FailTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that terminates the run in failure

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...

@singleton_type('agent_session')
class BlameTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that attributes failure to a dependency node via a blame target

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...

@singleton_type('agent_session')
class RunTestsTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Established that each tool has a name which the agent uses to execute the tool
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executed with a set of actual parameter bindings to produce a response

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.
"""
        ...
