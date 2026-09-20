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
import agent_config
import dag_subgraph
import sandbox

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
- [RunController] The run controller installs a check file tool that updates verification results if outdated, presenting verification outcomes to the agent and failing when verification failed.
- [RunController] The run controller installs a blame tool when blame targets are configured, attributing task failure to an upstream dependency node.
- [RunController] The run controller installs a get work tool that retrieves active dirty nodes, materializes startup templates, and delivers the session task prompt.

GROUNDING_ARGUMENT:
- As an agent_session singleton, RunController installs run control tools and exposes verification check sequences delegated from imported agent_node_config.NodeConfig, coordinating with tool_provider.ToolManager, sandbox_file_editor.EditManager, and dag_storage.DagStorage in the same session lifecycle tier, resolving session target nodes by alias, relative path, or unique filename.
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
Installs submit, fail, check file, and get work tools unconditionally, advance tool when guide step mode is active, and blame tool when blame targets are configured

FRESH_REQUIREMENTS:
- The run controller unconditionally installs the submit tool, fail tool, check file tool, and get work tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured.
- Verification checks exposed by the run controller include the session verification checks from node config.
- Session targets are matched by alias, relative path, or unique filename against open session targets.
- When a target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted target.
- When a target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.
- Tool execution fails when a target parameter is omitted and cannot be defaulted, or when the specified target parameter does not match an open session target, reminding the agent to specify an open target.
- Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution.
- When blame, submit, or fail is successfully called on a submit target and other submit targets remain, resolving the target produces a non-terminating response with a reminder listing remaining submit targets left for the agent to handle formatted via the template formatter.
- When all session targets are resolved, resolving a target produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.
- When all session targets are resolved, resolving a target produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.

GROUNDING_ARGUMENT:
- Reads step mode, blame targets, and verification checks from imported agent_node_config.NodeConfig, and installs SubmitTool, FailTool, CheckFileTool, GetWorkTool, optionally AdvanceTool, and optionally BlameTool directly into imported tool_provider.ToolManager in the same session lifecycle tier.
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
- Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before advancing.
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
- The submit tool is named `submit`, accepting a target parameter and a text change summary parameter, and shares a constant suppression key `submit`.
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
- Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.
- Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
- Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool targeting the submitted target with reasoning text indicating that verification results must be inspected before submitting.
- Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
- Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
- Tool execution marks the target as submitted and resolves the target.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings directly, extracts target and change_summary, resolves omitted targets against the single session read-write file, remaining unsubmitted read-write file, or last read or written path via imported sandbox_file_editor.EditManager, queries step mode from imported agent_node_config.NodeConfig and steps remaining from imported sandbox_guide_delivery.GuideDelivery returning a failure response specifying AdvanceTool as follow_up_tool_call if steps remain, inspects workspace modifications via imported sandbox_file_editor.EditManager, evaluates verification checks via RunController.evaluate_verification in the same session tier, sanitizes diagnostics through imported agent_file_alias.AliasManager, formats remaining open targets with template_format.TemplateFormatter, attaches suppression key 'submit', and produces a response indicating success.
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
- The fail tool is named `fail`, accepting a target parameter and a text explanation parameter.
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
- Executing the fail tool marks the target as failed and resolves the target.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings directly, extracts target and explanation, resolves omitted targets against the single session read-write file, remaining unsubmitted read-write file, or last read or written path via imported sandbox_file_editor.EditManager, validates that the target matches an open session target in RunController, updates node state in RunController, formats remaining open targets with template_format.TemplateFormatter, and constructs a failure response.
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
- The blame tool is named `blame`, accepting a source target parameter, a file alias blame target parameter, and a text explanation parameter.

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
- Tool execution defaults the source target parameter to that session target when the blame target matches a configured blame target of an open session target.
- Tool execution defaults the blame target parameter to that target and the source target parameter to the session target configured with that blame target when the blame target parameter is omitted and the source target parameter matches a configured blame target.
- Tool execution defaults the source target parameter using session target defaulting rules when the source target parameter is omitted and cannot be inferred from the blame target.
- Tool execution fails if the blame target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
- Tool execution marks the blame target as attributed and resolves the source target on successful tool execution.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Receives actual parameter bindings, resolves the target and blame target via imported agent_file_alias.AliasManager, infers or defaults the source target from open nodes in RunController or via imported sandbox_file_editor.EditManager, validates the blame target against RunController.blame_targets in the same session lifecycle tier, updates node state in RunController, formats remaining open targets with template_format.TemplateFormatter, and constructs a feedback response.
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
class CheckFileTool(sandbox_run_control.CheckFileTool):
    """
PURPOSE:
Implements check file tool to evaluate and present verification results

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The check file tool is named `check_file`, accepting a path parameter (with src accepted as an alias), and shares a constant suppression key `check_file`.

GROUNDING_ARGUMENT:
- As an agent_session singleton, CheckFileTool evaluates verification checks via RunController, presenting results with suppression key 'check_file' in the same session lifecycle tier.
"""

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Name of the tool used by the agent

GROUNDING_ARGUMENT:
- Returns the literal string 'check_file'.
"""
        ...

    @property
    @override
    def path(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the session file path to check

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter.
"""
        ...

    @property
    @override
    def src(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter identifying the session file path to check as an alias of path

GROUNDING_ARGUMENT:
- Constant parameter descriptor configured with alias manager converter matching path.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Description of the tool informing the agent why and when to use it

GROUNDING_ARGUMENT:
- Returns a constant description informing the agent that checking files evaluates verification checks.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Parameters accepted by the tool

GROUNDING_ARGUMENT:
- Returns a set containing the optional path and src parameters.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Executes the check file tool, updating verification results and presenting them

FRESH_REQUIREMENTS:
- When the path parameter is omitted, the path parameter defaults using session target defaulting rules.
- Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.
- Tool execution reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous check file tool execution.
- Tool execution specifies a follow-up execution of the view file tool on the session source file (resolving to the specified path target if a read-write file, the last accessed read-write file, or the primary session read-write file) and reasoning text noting that verification passed and to advance or submit the session if correct, or noting that verification failed until files are updated, when workspace files have not been updated since the previous check file tool execution.
- Tool execution fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
- Tool execution produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Evaluates verification via RunController.evaluate_verification in the same session lifecycle tier, resolves the session source file against actual parameter bindings, the single session read-write file, remaining unsubmitted read-write file, or the last accessed file from imported sandbox_file_editor.EditManager, sanitizes diagnostics through imported agent_file_alias.AliasManager, formats failure instructions from imported sandbox_guide_delivery.GuideDelivery, attaches suppression key 'check_file', and constructs a tool_provider.Response presenting verification outcome alongside check output.
"""
        ...

@singleton_type('agent_session')
class GetWorkTool(sandbox_run_control.GetWorkTool):
    """
PURPOSE:
Implements get work tool to retrieve active dirty targets, materialize startup templates, and deliver the session task prompt

INHERITED_ASSUMPTIONS:
- [Tool] All parameters of a tool have unique names.

FRESH_REQUIREMENTS:
- The get work tool is named `get_work`, accepting an integer max batch size parameter.

GROUNDING_ARGUMENT:
- As an agent_session singleton, GetWorkTool retrieves dirty nodes from dag_storage.DagStorage and dag_subgraph.DagSubgraph in the system tier, updates agent_node_config.RoleConfig in the session tier, materializes startup templates via sandbox.Sandbox in the session tier, formats the task prompt via template_format.TemplateFormatter and RunController, and returns the response.
"""

    @property
    @override
    def max_batch_size(self) -> tool_provider.Parameter:
        """
PURPOSE:
Parameter specifying the maximum number of dirty nodes to process together

GROUNDING_ARGUMENT:
- Defined on self as an optional integer parameter.
"""
        ...

    @property
    @override
    def name(self) -> str:
        """
PURPOSE:
Name of the get work tool

GROUNDING_ARGUMENT:
- Defined on self as 'get_work'.
"""
        ...

    @property
    @override
    def description(self) -> str:
        """
PURPOSE:
Description of the get work tool

GROUNDING_ARGUMENT:
- Defined on self describing retrieval of active dirty targets and task prompt.
"""
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.Parameter]:
        """
PURPOSE:
Parameters accepted by the get work tool

GROUNDING_ARGUMENT:
- Returns the set of parameters accepted by self including max_batch_size.
"""
        ...

    @operation
    @override
    def execute_tool(self, actual_parameter_bindings: tool_provider.ActualParameterBindings) -> tool_provider.Response:
        """
PURPOSE:
Retrieves dirty nodes, materializes startup templates, and returns the task prompt

FRESH_REQUIREMENTS:
- Tool execution fails when open session targets remain, reminding the agent that open targets must be resolved before requesting new work.
- Tool execution obtains dirty nodes from dag storage and dag subgraph, updating the active nodes and execution version on role config, when no open targets remain.
- Tool execution produces an idle response indicating that no dirty nodes are ready if no dirty nodes are ready for cleaning.
- Tool execution materializes startup templates on disk, constructs the task prompt from dirty node definitions, guide instructions, and incoming messages from dag storage formatted via the template formatter, and returns the rendered task prompt when ready dirty nodes are obtained.

INHERITED_REQUIREMENTS:
- [Tool] When a parameter is required, an argument must be supplied for tool execution.
- [Tool] When tool execution fails, the content includes declarative error and diagnostic messages along with impersonal guidance on executing the tool correctly without second-person pronouns.

GROUNDING_ARGUMENT:
- Coordinates with RunController, agent_node_config.RoleConfig, dag_subgraph.DagSubgraph, sandbox.Sandbox, and template_format.TemplateFormatter, validating open target state, updating nodes, materializing templates, and formatting task prompt.
"""
        ...
