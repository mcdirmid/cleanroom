from typing import List, Set
from framework import operation, override, singleton_type
import dag_storage
import file_alias
import node_config
import sandbox_file_editor
import sandbox_guide_delivery
import sandbox_run_control
import tool_provider

@singleton_type('agent_session')
class RunController(sandbox_run_control.RunController):
    """
PURPOSE:
Implements run controller to install advance, fail, and optional blame tools, maintaining verification checks

INHERITED_REQUIREMENTS:
- [RunController] The run controller installs the advance tool and fail tool unconditionally, and installs the blame tool only when blame targets are configured.

GROUNDING_ARGUMENT:
- As an agent_session singleton, RunController installs run control tools and maintains verification check sequences, coordinating with imported node_config.NodeConfig and tool_provider.ToolManager in the same session lifecycle tier.
"""

    @property
    @override
    def verification_checks(self) -> List[sandbox_run_control.VerificationCheck]:
        """
PURPOSE:
Sequence of installed verification checks evaluated during session advancement

GROUNDING_ARGUMENT:
- Internal list maintained within the agent_session singleton, initialized empty and populated via mutable operation install_verification_check.
"""
        ...

    @property
    @override
    def blame_targets(self) -> Set[file_alias.BoundFile]:
        """
PURPOSE:
Configured set of upstream bound files eligible for blame attribution obtained from node config

GROUNDING_ARGUMENT:
- Delegated from imported collaborator node_config.NodeConfig.blame_targets in the same session lifecycle tier.
"""
        ...

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Installs advance and fail tools unconditionally, and blame tool when blame targets are configured in node config

FRESH_REQUIREMENTS:
- The run controller installs the advance tool and fail tool unconditionally, and installs the blame tool only when blame targets are configured in the node config.

GROUNDING_ARGUMENT:
- Reads blame targets from imported node_config.NodeConfig, and installs AdvanceTool, FailTool, and BlameTool directly into imported tool_provider.ToolManager in the same session lifecycle tier.
"""
        ...

    @operation
    @override
    def install_verification_check(self, check: sandbox_run_control.VerificationCheck) -> None:
        """
PURPOSE:
Installs a verification check to be evaluated during session advancement

FRESH_REQUIREMENTS:
- Installing a verification check appends it to the sequence of checks evaluated by the advance tool.

INHERITED_REQUIREMENTS:
- [RunController] Installing a verification check adds it to the verification checks evaluated during session advancement.

GROUNDING_ARGUMENT:
- Receives check directly as a parameter and appends it to self.verification_checks on the agent_session singleton.
"""
        ...

@singleton_type('agent_session')
class AdvanceTool(sandbox_run_control.AdvanceTool):
    """
PURPOSE:
Implements advance tool to coordinate progressive steps, verify state, and complete the run

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The advance tool is named `advance`.
- The advance tool change summary parameter uses a string parameter converter to accept text.

GROUNDING_ARGUMENT:
- As an agent_session singleton, AdvanceTool coordinates progressive guidance delivery, verification check evaluations, and session completion, interacting with imported sandbox_guide_delivery.GuideDelivery, sandbox_file_editor.EditManager, and RunController in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the advance tool is named advance

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('advance').
"""
        ...

    @property
    def change_summary(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter accepting text describing changes made during the session

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to advance guide steps or evaluate verification checks and change summary

FRESH_REQUIREMENTS:
- A call to the advance tool can be injected at agent session start when using step mode to deliver initial step content, executing without requiring a change summary.
- When progressive guide delivery is configured and steps remain in guide delivery, executing the advance tool advances the guide step and returns the next step content without terminating the run.
- When no guide steps remain or guide delivery is not configured, executing the advance tool queries the edit manager and fails if workspace files were modified and the change summary is empty.
- When verification checks are installed, executing the advance tool evaluates each check in order and fails if any verification check does not pass.
- When no workspace files were modified, no verification checks were installed, and no change summary was provided, executing the advance tool fails.
- On successful advance tool execution when no guide steps remain, the response indicates termination.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, queries steps remaining and advances steps via imported sandbox_guide_delivery.GuideDelivery, queries file modification state from imported sandbox_file_editor.EditManager, evaluates checks in RunController.verification_checks in the same session lifecycle tier, and validates change summary content.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool

GROUNDING_ARGUMENT:
- Constant tool description string.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation

GROUNDING_ARGUMENT:
- Set composed of self's constant parameter descriptor (change_summary).
"""
        ...

@singleton_type('agent_session')
class FailTool(sandbox_run_control.FailTool):
    """
PURPOSE:
Implements fail tool to terminate run in failure

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The fail tool is named `fail`.
- The fail tool explanation parameter uses a string parameter converter to accept text.

GROUNDING_ARGUMENT:
- As an agent_session singleton, FailTool terminates the session in failure without requiring external singleton dependencies.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the fail tool is named fail

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('fail').
"""
        ...

    @property
    def explanation(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter accepting a text explanation of why the run failed

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to produce a terminating failure response

FRESH_REQUIREMENTS:
- Executing the fail tool produces a terminating response carrying the explanation.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings directly, extracts the explanation parameter, and constructs a terminating failure response.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool

GROUNDING_ARGUMENT:
- Constant tool description string.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation

GROUNDING_ARGUMENT:
- Set composed of self's constant parameter descriptor (explanation).
"""
        ...

@singleton_type('agent_session')
class BlameTool(sandbox_run_control.BlameTool):
    """
PURPOSE:
Implements blame tool to attribute failure to a dependency node

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The blame tool is named `blame`.
- The blame tool blame target parameter uses the alias manager to convert a file alias.
- The blame tool explanation parameter uses a string parameter converter to accept text.

GROUNDING_ARGUMENT:
- As an agent_session singleton, BlameTool attributes prerequisite defects to dependency nodes, coordinating with RunController and imported file_alias.AliasManager in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the blame tool is named blame

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('blame').
"""
        ...

    @property
    def blame_target(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target bound file

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    def explanation(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter accepting a text explanation of the prerequisite defect

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to validate blame target and produce a terminating feedback response

FRESH_REQUIREMENTS:
- Executing the blame tool fails if the target does not match any configured blame target, listing available blame targets.
- On successful blame tool execution, the response indicates termination attributing feedback to the blame target owning node.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves the blame target via imported file_alias.AliasManager, validates the target against RunController.blame_targets in the same session lifecycle tier, and constructs a terminating feedback response.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Established that each tool has a description which informs the agent why and when to use the tool

GROUNDING_ARGUMENT:
- Constant tool description string.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Established that each tool defines input parameters accepted for its invocation

GROUNDING_ARGUMENT:
- Set composed of self's constant parameter descriptors (blame_target, explanation).
"""
        ...
