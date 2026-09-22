from typing import Protocol, Sequence, Set
from framework import operation, override, poly_type, singleton_type
import dag_storage
import agent_file_alias
import agent_node_config
import sandbox_file_editor
import sandbox_guide_delivery
import tool_provider

@singleton_type('agent_session')
class RunController(Protocol):
    """
PURPOSE:
Defined as an agent session service that installs run control tools and exposes verification checks

FRESH_REQUIREMENTS:
- The run controller exposes verification checks that validate session criteria.
- The run controller caches verification evaluation results alongside edit manager file hashes for target nodes, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.
- The run controller installs an argument-free check files tool named check_files that updates verification results if outdated, evaluates verification checks across all open targets and modified workspace files, presents aggregated verification outcomes to the agent, tracks last tested file hashes, and fails when verification failed.
- The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
- The run controller installs a submit tool which is a resolve tool that concludes active nodes upon passing verification, marks the resolve target clean in the current get work turn, accepting a text change summary parameter, and enforces change documentation.
- The run controller installs a fail tool which is a resolve tool that terminates the run in failure, accepting a text explanation parameter.
- The run controller installs a blame tool which is a resolve tool, when blame targets are configured, attributing task failure to an upstream dependency node, accepting a file alias blame target parameter and a text explanation parameter.
- The run controller installs a get work tool that retrieves active dirty nodes, materializes startup templates, accepting an integer max batch size parameter, and delivers the session task prompt.
"""

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
PURPOSE:
Verification checks configured for the session
"""
        ...

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Upstream bound files that can be attributed when prerequisite defects occur
"""
        ...

@singleton_type('agent_session')
class CheckFilesTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as an argument-free tool named check_files that updates verification results if outdated, evaluates verification checks across all open targets and modified workspace files, presenting aggregated verification outcomes to the agent and failing when verification failed

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

@poly_type
class ResolveTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a polymorphic tool service for resolving active nodes in an agent session

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def resolve_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Parameter identifying the active node being resolved
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
class SubmitTool(ResolveTool, Protocol):
    """
PURPOSE:
Defined as a tool that concludes active nodes upon passing verification and enforces change documentation

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def change_summary(self) -> tool_provider.Parameter[str, str]:
        """
PURPOSE:
Parameter describing workspace file modifications
"""
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Parameter identifying the active node being resolved
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
class FailTool(ResolveTool, Protocol):
    """
PURPOSE:
Defined as a tool that terminates the run in failure

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def explanation(self) -> tool_provider.Parameter[str, str]:
        """
PURPOSE:
Parameter accepting a text explanation of why the run failed
"""
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Parameter identifying the active node being resolved
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
class BlameTool(ResolveTool, Protocol):
    """
PURPOSE:
Defined as a tool that attributes task failure to an upstream dependency node via a blame target

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def blame_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Parameter identifying the target bound file being blamed
"""
        ...

    @property
    def explanation(self) -> tool_provider.Parameter[str, str]:
        """
PURPOSE:
Parameter accepting a text explanation of the prerequisite defect
"""
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.Parameter[agent_file_alias.FileAlias, str]:
        """
PURPOSE:
Parameter identifying the active node being resolved
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
class GetWorkTool(tool_provider.Tool, Protocol):
    """
PURPOSE:
Defined as a tool that retrieves active dirty nodes, materializes startup templates, and delivers the session task prompt

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.
"""

    @property
    def max_batch_size(self) -> tool_provider.Parameter[int, int]:
        """
PURPOSE:
Parameter specifying the maximum number of dirty nodes to batch in a session
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
