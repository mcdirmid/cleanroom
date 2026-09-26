from typing import Protocol, Sequence, Set
from framework import operation, override, poly_type, singleton_type
import agent_file_alias
import agent_node_config
import dag_storage
import sandbox_file_editor
import sandbox_guide_delivery
import tool_provider


@singleton_type("agent_session")
class RunController(Protocol):
    """Defined as an agent session service that installs run control tools and exposes verification checks."""

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Verification checks configured for the session.

        GROUNDING_PROVISIONS:
        - knows("verification_checks", Sequence[agent_node_config.VerificationCheck]): Exposes session verification checks to satisfy requirement 2.
        """
        ...



@singleton_type("agent_session")
class CheckFilesTool(tool_provider.Tool, Protocol):
    """Argument-free tool named check_files that updates verification results and evaluates checks."""

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response.

        GROUNDING_PROVISIONS:
        - action("execute_check_files", tool_provider.ToolResponse): Evaluates verification checks to satisfy requirement 4.
        """
        ...


@singleton_type("agent_session")
class AdvanceTool(tool_provider.Tool, Protocol):
    """Tool that coordinates step progression through guide delivery when guide step mode is active."""

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response.

        GROUNDING_PROVISIONS:
        - action("execute_advance", tool_provider.ToolResponse): Advances guide steps to satisfy requirement 5.
        """
        ...


@poly_type
class ResolveTool(tool_provider.Tool, Protocol):
    """Polymorphic tool service for resolving active nodes in an agent session."""

    @property
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved."""
        ...

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response."""
        ...


@singleton_type("agent_session")
class SubmitTool(ResolveTool, Protocol):
    """Concludes active nodes upon passing verification and enforces change documentation."""

    @property
    def change_summary(self) -> tool_provider.ToolParameter[str, str]:
        """Parameter describing workspace file modifications."""
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved."""
        ...

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response.

        GROUNDING_PROVISIONS:
        - action("execute_submit", tool_provider.ToolResponse): Concludes active node to satisfy requirement 6.
        """
        ...


@singleton_type("agent_session")
class FailTool(ResolveTool, Protocol):
    """Terminates the run in failure."""

    @property
    def explanation(self) -> tool_provider.ToolParameter[str, str]:
        """Parameter accepting a text explanation of why the run failed."""
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved."""
        ...

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response.

        GROUNDING_PROVISIONS:
        - action("execute_fail", tool_provider.ToolResponse): Fails node to satisfy requirement 7.
        """
        ...


@singleton_type("agent_session")
class BlameTool(ResolveTool, Protocol):
    """Attributes task failure to an upstream dependency node via a blame target."""

    @property
    def blame_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the target bound file being blamed."""
        ...

    @property
    def explanation(self) -> tool_provider.ToolParameter[str, str]:
        """Parameter accepting a text explanation of the prerequisite defect."""
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved."""
        ...

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response.

        GROUNDING_PROVISIONS:
        - action("execute_blame", tool_provider.ToolResponse): Attributes failure to upstream target to satisfy requirement 8.
        """
        ...


@singleton_type("agent_session")
class GetWorkTool(tool_provider.Tool, Protocol):
    """Retrieves active dirty nodes, materializes startup templates, and delivers task prompt."""

    @property
    def max_batch_size(self) -> tool_provider.ToolParameter[int, int]:
        """Parameter specifying the maximum number of dirty nodes to batch in a session."""
        ...

    @property
    @override
    def name(self) -> str:
        """Name used by agent to execute the tool."""
        ...

    @property
    @override
    def description(self) -> str:
        """Description informing why and when to use the tool."""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation."""
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executed with actual parameter bindings to produce a response.

        GROUNDING_PROVISIONS:
        - action("execute_get_work", tool_provider.ToolResponse): Retrieves dirty nodes and delivers prompt to satisfy requirement 9.
        """
        ...


