from typing import Sequence, Set, Tuple
from framework import operation, override, singleton_type
import dag_storage
import agent_file_alias
import agent_node_config
import sandbox_file_editor
import sandbox_guide_delivery
import sandbox_run_control
import template_format
import tool_provider

@singleton_type('agent_session')
class RunController(sandbox_run_control.RunController):
    """
PURPOSE:
Implements run controller to install advance, submit, fail, and optional blame tools, managing cached verification check results

INHERITED_REQUIREMENTS:
- [RunController] The run controller exposes verification checks that validate session criteria.
- [RunController] The run controller caches verification evaluation results alongside the edit manager file update revision, reusing the cached verification outcome as long as no workspace files have been updated since that evaluation.
- [RunController] The run controller installs an advance tool when guide step mode is active, coordinating step progression through guide delivery upon passing verification.
- [RunController] The run controller installs a submit tool that concludes target processing upon passing verification and enforces change documentation.
- [RunController] The run controller installs a fail tool that terminates the run in failure.
- [RunController] The run controller installs a run tests tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
- [RunController] The run controller installs a blame tool when blame targets are configured, attributing task failure to an upstream dependency node.

GROUNDING_ARGUMENT:
- As an agent_session singleton, RunController installs run control tools and exposes verification check sequences delegated from imported agent_node_config.NodeConfig, coordinating with tool_provider.ToolManager, sandbox_file_editor.EditManager, and dag_storage.DagStorage in the same session lifecycle tier.
"""

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """
PURPOSE:
Sequence of verification checks evaluated during session advancement

GROUNDING_ARGUMENT:
- Delegated from imported collaborator agent_node_config.NodeConfig.verification_checks in the same session lifecycle tier.
"""
        ...

    @property
    @override
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        """
PURPOSE:
Configured set of upstream bound files eligible for blame attribution obtained from node config

GROUNDING_ARGUMENT:
- Delegated from imported collaborator agent_node_config.NodeConfig.blame_targets in the same session lifecycle tier.
"""
        ...

    @operation
    def initialize(self) -> None:
        """
PURPOSE:
Installs submit, fail, and run tests tools unconditionally, advance tool when guide step mode is active, and blame tool when blame targets are configured

FRESH_REQUIREMENTS:
- The run controller unconditionally installs the submit tool, fail tool, and run tests tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
- Verification checks exposed by the run controller include the session verification checks from node config.

GROUNDING_ARGUMENT:
- Reads step mode, blame targets, and verification checks from imported agent_node_config.NodeConfig, and installs SubmitTool, FailTool, RunTestsTool, optionally AdvanceTool, and optionally BlameTool directly into imported tool_provider.ToolManager in the same session lifecycle tier.
"""
        ...

    @operation
    def evaluate_verification(self) -> Tuple[bool, str]:
        """
PURPOSE:
Evaluates verification checks with file update revision caching

FRESH_REQUIREMENTS:
- Evaluation of verification checks is cached alongside the edit manager file update revision.
- Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation.
- When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.

GROUNDING_ARGUMENT:
- Tracks cached verification outcome and revision on self, inspecting file_update_revision from imported sandbox_file_editor.EditManager, executing self.verification_checks and caching results when revision changes.
"""
        ...

@singleton_type('agent_session')
class AdvanceTool(sandbox_run_control.AdvanceTool):
    """
PURPOSE:
Implements advance tool to coordinate self-contained guide progression

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`.

GROUNDING_ARGUMENT:
- As an agent_session singleton, AdvanceTool coordinates guide step progression, interacting with imported sandbox_guide_delivery.GuideDelivery, sandbox_file_editor.EditManager, and RunController in the same session lifecycle tier.
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
Accepts no parameters

GROUNDING_ARGUMENT:
- Constant empty set.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to advance guide steps and report progress or failure diagnostics

FRESH_REQUIREMENTS:
- On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results.
- On subsequent executions, executing the advance tool updates verification results if outdated.
- Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool with reasoning text indicating that verification results must be inspected before advancing.
- Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
- Tool execution fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
- Tool execution produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Evaluates verification via RunController.evaluate_verification in the same session lifecycle tier, queries steps remaining and advances steps via imported sandbox_guide_delivery.GuideDelivery, checks workspace modifications via imported sandbox_file_editor.EditManager, sanitizes diagnostics through imported agent_file_alias.AliasManager, attaches suppression key 'advance', and specifies SubmitTool as follow_up_tool_call when no steps remain and no files were modified.
"""
        ...

@singleton_type('agent_session')
class SubmitTool(sandbox_run_control.SubmitTool):
    """
PURPOSE:
Implements submit tool to evaluate target completion criteria, in-session dependencies, and verification checks

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The submit tool is named `submit`, accepting an optional target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
- The submit tool change summary parameter uses a string parameter converter to accept text.

GROUNDING_ARGUMENT:
- As an agent_session singleton, SubmitTool validates session completion criteria, interacting with imported sandbox_guide_delivery.GuideDelivery, sandbox_file_editor.EditManager, agent_node_config.NodeConfig, template_format.TemplateFormatter, and RunController in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Establishes that the submit tool is named submit

GROUNDING_ARGUMENT:
- Constant tool schema identifier ('submit').
"""
        ...

    @property
    @override
    def target(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target file being submitted

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def change_summary(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter describing workspace file modifications

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with string parameter converter.
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
- Set composed of target and change_summary parameter descriptors.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Implements execute_tool to evaluate completion criteria, in-session dependencies, and verification checks

FRESH_REQUIREMENTS:
- Executing the submit tool updates verification results if outdated.
- In multi-target sessions, tool execution fails when the target parameter is omitted or does not match an open session target, reminding the agent to specify an open target.
- Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.
- Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
- Tool execution fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool with reasoning text indicating that verification results must be inspected before submitting.
- Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
- Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
- Tool execution marks the target as submitted, locks the target read-write files in the edit manager against modification, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings directly, extracts target and change_summary, queries step mode from imported agent_node_config.NodeConfig and steps remaining from imported sandbox_guide_delivery.GuideDelivery returning a failure response specifying AdvanceTool as follow_up_tool_call if steps remain, inspects workspace modifications via imported sandbox_file_editor.EditManager, evaluates verification checks via RunController.evaluate_verification in the same session tier, sanitizes diagnostics through imported agent_file_alias.AliasManager, formats remaining open targets with template_format.TemplateFormatter, attaches suppression key 'submit', and produces a response indicating success.
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
- As an agent_session singleton, FailTool terminates the session in failure, coordinating with RunController and template_format.TemplateFormatter in the same session lifecycle tier.
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
    @override
    def target(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the session target file being failed

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
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
Implements execute_tool to produce a failure response

FRESH_REQUIREMENTS:
- Executing the fail tool marks the target as failed, locks the target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings directly, extracts target and explanation, updates node state in RunController, formats remaining open targets with template_format.TemplateFormatter, and constructs a failure response.
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
- Set composed of self's constant parameter descriptors (target, explanation).
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
- As an agent_session singleton, BlameTool attributes prerequisite defects to dependency nodes, coordinating with RunController, template_format.TemplateFormatter, and imported agent_file_alias.AliasManager in the same session lifecycle tier.
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
    @override
    def target(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the session target file being blamed from

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def blame_target(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the target bound file

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
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
- Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
- On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves the target and blame target via imported agent_file_alias.AliasManager, validates the blame target against RunController.blame_targets in the same session lifecycle tier, updates node state in RunController, formats remaining open targets with template_format.TemplateFormatter, and constructs a feedback response.
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
- Set composed of self's constant parameter descriptors (target, blame_target, explanation).
"""
        ...

@singleton_type('agent_session')
class RunTestsTool(sandbox_run_control.RunTestsTool):
    """
PURPOSE:
Implements run tests tool to evaluate and present verification results

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The run tests tool is named `run_tests`, accepting an optional target parameter, and shares a constant suppression key `run_tests`.

GROUNDING_ARGUMENT:
- As an agent_session singleton, RunTestsTool evaluates verification checks via RunController, presenting results with suppression key 'run_tests' in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Name of the tool used by the agent

GROUNDING_ARGUMENT:
- Returns the literal string 'run_tests'.
"""
        ...

    @property
    @override
    def target(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the session target file to run tests for

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Description of the tool informing the agent why and when to use it

GROUNDING_ARGUMENT:
- Returns a constant description informing the agent that running tests evaluates verification checks.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Parameters accepted by the tool

GROUNDING_ARGUMENT:
- Returns a set containing the optional target parameter.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executes the run tests tool, updating verification results and presenting them

FRESH_REQUIREMENTS:
- Executing the run tests tool updates verification results if outdated.
- When a target is specified, executing the run tests tool evaluates verification checks for that target.
- Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous run tests tool execution.
- Specifies a follow-up execution of the view file tool on the session source file and reasoning text noting that verification passed without permission to run more tests and to advance or submit the session if correct, or noting that verification failed without permission to run more tests until files are updated, when workspace files have not been updated since the previous run tests tool execution.
- Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
- Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Evaluates verification via RunController.evaluate_verification in the same session lifecycle tier, sanitizes diagnostics through imported agent_file_alias.AliasManager, formats failure instructions from imported sandbox_guide_delivery.GuideDelivery, attaches suppression key 'run_tests', and constructs a tool_provider.Response presenting verification outcome alongside check output.
"""
        ...
