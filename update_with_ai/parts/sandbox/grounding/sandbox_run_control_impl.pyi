from typing import Sequence, Set, Tuple, Self
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


@singleton_type("agent_session")
class RunController(sandbox_run_control.RunController):
    """Implements run controller to install advance, submit, fail, and optional blame tools, managing cached verification check results.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, RunController installs run control tools and exposes verification check sequences delegated from imported agent_node_config.NodeConfig, coordinating with tool_provider.ToolManager, sandbox_file_editor.EditManager, and dag_storage.DagStorage in the same session lifecycle tier, resolving active nodes by file alias, relative path, or unique filename.
    """

    @property
    @override
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        """Sequence of verification checks evaluated during session advancement.

        GROUNDING_PROVISIONS:
        - knows("verification_checks", Sequence[agent_node_config.VerificationCheck]): Exposes session verification checks to satisfy requirement 2.

        GROUNDING_ARGUMENT:
        - knows("verification_checks", Self) :- knows("verification_checks", agent_node_config.NodeConfig).
        """
        ...

    @operation
    def initialize(self) -> None:
        """Installs run control tools based on session configuration.

        REQUIREMENTS:
        - Tools cannot be configured against non-role/agent-specific state; the run controller installs submit, fail, check files, get work, and blame tools unconditionally, and installs advance tool when guide step mode is active.
        - Verification checks exposed by the run controller include the session verification checks from node config.
        - A resolve tool defines a file alias resolve target parameter (with target accepted as an alias), and matches the resolve target parameter by file alias, relative path, or unique filename against open active nodes.
        - When the resolve target parameter is omitted, it defaults to the single session read-write file or remaining unsubmitted active node.
        - When the resolve target parameter is omitted, it defaults to the last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open active node.
        - Tool execution fails when the resolve target parameter is omitted and cannot be defaulted, or when the specified resolve target parameter does not match an open active node, reminding the agent to specify an open target.
        - Tool execution fails when an in-batch dependency of the resolve target is not clean in the current get work turn, reminding the agent that in-batch dependencies must be submitted before dependent targets.
        - Resolving an active node locks the resolve target read-write files in the edit manager against subsequent modification.
        - Automatically marks in-batch dependent nodes as failed and locks their read-write files upon node failure or blame attribution.
        - Produces a non-terminating response with a reminder listing remaining active nodes formatted via the template formatter when other active nodes remain.
        - When all active nodes are resolved, resolving an active node produces a terminating response indicating that the session completed successfully for submitted nodes, carrying the explanation for failed nodes, or attributing defect feedback to the blame target owning node for blamed nodes, when mcp mode is inactive.
        - When all active nodes are resolved, resolving an active node produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.

        GROUNDING_PROVISIONS:
        - action("initialize_run_control", None): Installs tools and sets up run controller to satisfy requirement 1.

        GROUNDING_ARGUMENT:
        - action("initialize_run_control", Self) :- action("install_tool", tool_provider.ToolManager), knows("is_step_mode", agent_node_config.NodeConfig).
        """
        ...

    @operation
    def evaluate_verification(self) -> Tuple[bool, str]:
        """Evaluates verification checks with file update revision caching.

        Returns:
            A tuple of boolean pass status and diagnostic feedback string.

        REQUIREMENTS:
        - Evaluation of verification checks for an active node is cached alongside the edit manager file hash of the target node read-write file.
        - Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when the target read-write file hash has changed since the previous evaluation.
        - When the target read-write file hash has not changed since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.

        GROUNDING_PROVISIONS:
        - action("evaluate_verification", Tuple[bool, str]): Evaluates verification checks to satisfy requirement 2.

        GROUNDING_ARGUMENT:
        - action("evaluate_verification", Self) :- knows("verification_checks", Self), action("file_hash", sandbox_file_editor.EditManager).
        """
        ...


@singleton_type("agent_session")
class CheckFilesTool(sandbox_run_control.CheckFilesTool):
    """Implements argument-free check files tool to evaluate and present verification results.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, CheckFilesTool evaluates verification checks via RunController, presenting results with suppression key 'check_files' in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Name of the tool used by the agent.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Returns 'check_files' to satisfy requirement 3.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Description of the tool informing the agent why and when to use it.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Returns tool description string.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Parameters accepted by the tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Returns empty parameter set.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Executes the check files tool, updating verification results and presenting them.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool response with verification feedback.

        REQUIREMENTS:
        - Executing the check files tool updates verification results if outdated and evaluates verification checks across all open targets and modified workspace files.
        - Tool execution reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when target read-write file hashes have not changed since the previous check files tool execution.
        - Tool execution fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.
        - Tool execution produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.

        GROUNDING_PROVISIONS:
        - action("execute_check_files", tool_provider.ToolResponse): Executes check files to satisfy requirements 4, 5, and 6.

        GROUNDING_ARGUMENT:
        - action("execute_check_files", Self) :- action("evaluate_verification", sandbox_run_control.RunController), action("sanitize_text", agent_file_alias.AliasManager).
        """
        ...


@singleton_type("agent_session")
class AdvanceTool(sandbox_run_control.AdvanceTool):
    """Implements advance tool to coordinate self-contained guide progression.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, AdvanceTool coordinates guide step progression, interacting with imported sandbox_guide_delivery.GuideDelivery, sandbox_file_editor.EditManager, and RunController in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Establishes that the advance tool is named advance.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Returns 'advance' to satisfy requirement 8.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Established that each tool has a description which informs the agent why and when to use the tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Returns tool description string.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Accepts no parameters.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Returns empty parameter set.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Implements execute_tool to advance guide steps and report progress or failure diagnostics.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool response with next step instructions or failure feedback.

        REQUIREMENTS:
        - Tool execution fails when verification has not been evaluated for the current workspace files or is failing, evaluating verification results and repeating the primer and summary content alongside failure diagnostics through guide delivery on the first step, reminding the agent that the check files tool should be called first, and specifying a follow-up execution of the check files tool with reasoning text indicating that verification results must be inspected before advancing.
        - Tool execution advances guide delivery and delivers the next step section when verification is passing and guide steps remain.
        - Tool execution fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.
        - Tool execution produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.

        GROUNDING_PROVISIONS:
        - action("execute_advance", tool_provider.ToolResponse): Executes advance tool to satisfy requirements 9, 10, 11, 12, and 13.

        GROUNDING_ARGUMENT:
        - action("execute_advance", Self) :- action("evaluate_verification", sandbox_run_control.RunController), action("advance_step", sandbox_guide_delivery.GuideDelivery), knows("has_modifications", sandbox_file_editor.EditManager).
        """
        ...


@singleton_type("agent_session")
class SubmitTool(sandbox_run_control.SubmitTool):
    """Implements submit tool to evaluate target completion criteria, in-session dependencies, and verification checks.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, SubmitTool validates session completion criteria, interacting with imported sandbox_guide_delivery.GuideDelivery, sandbox_file_editor.EditManager, agent_node_config.NodeConfig, template_format.TemplateFormatter, and RunController in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Establishes that the submit tool is named submit.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Returns 'submit' to satisfy requirement 18.
        """
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved.

        GROUNDING_PROVISIONS:
        - knows("resolve_target_parameter", tool_provider.ToolParameter): Exposes resolve target parameter to satisfy requirement 18.

        GROUNDING_ARGUMENT:
        - knows("resolve_target_parameter", Self) :- action("convert", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def change_summary(self) -> tool_provider.ToolParameter[str, str]:
        """Parameter describing workspace file modifications.

        GROUNDING_IMPLEMENTS:
        - knows("change_summary_parameter", tool_provider.ToolParameter): Exposes change summary parameter to satisfy requirement 18.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Established that each tool has a description which informs the agent why and when to use the tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Returns tool description string.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Returns resolve_target and change_summary parameters.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Implements execute_tool to evaluate completion criteria, in-session dependencies, and verification checks.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool response indicating outcome or failure feedback.

        REQUIREMENTS:
        - Executing the submit tool updates verification results if outdated.
        - Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.
        - Tool execution fails when verification is failing, reminding the agent that the check files tool should be called first and specifying a follow-up execution of the check files tool targeting the resolve target with reasoning text indicating that verification results must be inspected before submitting.
        - Tool execution fails when an initial implementation change is assigned to the target node and no workspace files were modified, reminding the agent that workspace files must be modified to implement the change before submitting.
        - Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.
        - Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.
        - Tool execution marks the resolve target clean and submitted in the current get work turn and resolves the active node.

        GROUNDING_PROVISIONS:
        - action("execute_submit", tool_provider.ToolResponse): Executes submit to satisfy requirements 19, 20, 21, 22, and 23.

        GROUNDING_ARGUMENT:
        - action("execute_submit", Self) :- action("evaluate_verification", sandbox_run_control.RunController), knows("has_steps_remaining", sandbox_guide_delivery.GuideDelivery), knows("has_modifications", sandbox_file_editor.EditManager), action("lock_file", sandbox_file_editor.EditManager).
        """
        ...


@singleton_type("agent_session")
class FailTool(sandbox_run_control.FailTool):
    """Implements fail tool to terminate run in failure.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, FailTool terminates the session in failure, coordinating with RunController and template_format.TemplateFormatter in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Establishes that the fail tool is named fail.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Returns 'fail' to satisfy requirement 24.
        """
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved.

        GROUNDING_PROVISIONS:
        - knows("resolve_target_parameter", tool_provider.ToolParameter): Exposes resolve target parameter to satisfy requirement 24.

        GROUNDING_ARGUMENT:
        - knows("resolve_target_parameter", Self) :- action("convert", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def explanation(self) -> tool_provider.ToolParameter[str, str]:
        """Parameter accepting a text explanation of why the run failed.

        GROUNDING_IMPLEMENTS:
        - knows("explanation_parameter", tool_provider.ToolParameter): Exposes explanation parameter to satisfy requirement 24.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Implements execute_tool to produce a failure response.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool failure response.

        REQUIREMENTS:
        - Executing the fail tool marks the active node as failed and resolves the active node.

        GROUNDING_PROVISIONS:
        - action("execute_fail", tool_provider.ToolResponse): Executes fail to satisfy requirement 24.

        GROUNDING_ARGUMENT:
        - action("execute_fail", Self) :- action("lock_file", sandbox_file_editor.EditManager).
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Established that each tool has a description which informs the agent why and when to use the tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Returns tool description string.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Returns resolve_target and explanation parameters.
        """
        ...


@singleton_type("agent_session")
class BlameTool(sandbox_run_control.BlameTool):
    """Implements blame tool to attribute failure to a dependency node.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, BlameTool attributes prerequisite defects to dependency nodes, coordinating with RunController, template_format.TemplateFormatter, and imported agent_file_alias.AliasManager in the same session lifecycle tier.
    """

    @property
    @override
    def name(self) -> str:
        """Establishes that the blame tool is named blame.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Returns 'blame' to satisfy requirement 25.
        """
        ...

    @property
    @override
    def resolve_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the active node being resolved.

        GROUNDING_PROVISIONS:
        - knows("resolve_target_parameter", tool_provider.ToolParameter): Exposes resolve target parameter to satisfy requirement 25.

        GROUNDING_ARGUMENT:
        - knows("resolve_target_parameter", Self) :- action("convert", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def blame_target(self) -> tool_provider.ToolParameter[agent_file_alias.FileAlias, tool_provider.WireString]:
        """Parameter identifying the target bound file.

        GROUNDING_PROVISIONS:
        - knows("blame_target_parameter", tool_provider.ToolParameter): Exposes blame target parameter to satisfy requirement 25.

        GROUNDING_ARGUMENT:
        - knows("blame_target_parameter", Self) :- action("convert", agent_file_alias.AliasManager).
        """
        ...

    @property
    @override
    def explanation(self) -> tool_provider.ToolParameter[str, str]:
        """Parameter accepting a text explanation of the prerequisite defect.

        GROUNDING_IMPLEMENTS:
        - knows("explanation_parameter", tool_provider.ToolParameter): Exposes explanation parameter to satisfy requirement 25.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Implements execute_tool to validate blame target and produce a terminating feedback response.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool response with blame attribution feedback.

        REQUIREMENTS:
        - Tool execution defaults the resolve target parameter to that active node when the blame target matches a configured blame target of an open active node.
        - Tool execution defaults the blame target parameter to that target and the resolve target parameter to the active node configured with that blame target when the blame target parameter is omitted and the resolve target parameter matches a configured blame target.
        - Tool execution defaults the resolve target parameter using resolve target defaulting rules when the resolve target parameter is omitted and cannot be inferred from the blame target.
        - Tool execution fails if the blame target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.
        - Tool execution marks the blame target as attributed and resolves the active node on successful tool execution.

        GROUNDING_PROVISIONS:
        - action("execute_blame", tool_provider.ToolResponse): Executes blame to satisfy requirement 25.

        GROUNDING_ARGUMENT:
        - action("execute_blame", Self) :- knows("blame_targets", sandbox_run_control.RunController), action("lock_file", sandbox_file_editor.EditManager).
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Established that each tool has a description which informs the agent why and when to use the tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Returns tool description string.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Input parameters accepted for invocation.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Returns resolve_target, blame_target, and explanation parameters.
        """
        ...


@singleton_type("agent_session")
class GetWorkTool(sandbox_run_control.GetWorkTool):
    """Implements get work tool to retrieve active dirty targets, materialize startup templates, and deliver the session task prompt.

    GROUNDING_ARGUMENT:
    - As an agent_session singleton, GetWorkTool retrieves dirty nodes from dag_storage.DagStorage and dag_subgraph.DagSubgraph in the system tier, updates agent_node_config.RoleConfig in the session tier, materializes startup templates via sandbox.Sandbox in the session tier, formats the task prompt via template_format.TemplateFormatter and RunController, and returns the response.
    """

    @property
    @override
    def max_batch_size(self) -> tool_provider.ToolParameter[int, int]:
        """Parameter specifying the maximum number of dirty nodes to process together.

        GROUNDING_IMPLEMENTS:
        - knows("max_batch_size_parameter", tool_provider.ToolParameter): Exposes max batch size parameter to satisfy requirement 26.
        """
        ...

    @property
    @override
    def name(self) -> str:
        """Name of the get work tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_name", str): Returns 'get_work' to satisfy requirement 26.
        """
        ...

    @property
    @override
    def description(self) -> str:
        """Description of the get work tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_description", str): Returns description string.
        """
        ...

    @property
    @override
    def parameters(self) -> Set[tool_provider.ToolParameter]:
        """Parameters accepted by the get work tool.

        GROUNDING_IMPLEMENTS:
        - knows("tool_parameters", Set[tool_provider.ToolParameter]): Returns parameters accepted by get work tool.
        """
        ...

    @operation
    @override
    def execute_tool(
        self, actual_parameter_bindings: tool_provider.ActualParameterBindings
    ) -> tool_provider.ToolResponse:
        """Retrieves dirty nodes, materializes startup templates, and returns the task prompt.

        Args:
            actual_parameter_bindings: Resolved tool parameter values.

        Returns:
            The tool response with work assignments or idle message.

        REQUIREMENTS:
        - Tool execution fails when open active nodes remain, reminding the agent that open nodes must be resolved before requesting new work.
        - Tool execution obtains dirty nodes from dag storage and dag subgraph, updating the active nodes and execution version on role config, when no open active nodes remain.
        - Tool execution produces an idle response indicating that no dirty nodes are ready if no dirty nodes are ready for cleaning.
        - Tool execution materializes startup templates on disk, initializes guide delivery and resets guide advance state for the assigned batch, and returns the rendered task primer mapping source files to grounding files with guide file attribution, incoming messages, and instructions to read the guide file for alignment guidance when ready dirty nodes are obtained and guide step mode is inactive.
        - Tool execution materializes startup templates on disk, initializes guide delivery, records the task primer in guide delivery, and returns the task primer mapping source files to grounding files, guide summary, incoming messages, and instructions to call the advance tool when done making edits without guide file citation and without specifying a follow-up execution of the advance tool when ready dirty nodes are obtained and guide step mode is active.

        GROUNDING_PROVISIONS:
        - action("execute_get_work", tool_provider.ToolResponse): Executes get work to satisfy requirement 26.

        GROUNDING_ARGUMENT:
        - action("execute_get_work", Self) :- action("next_ready_batch", dag_subgraph.DagSubgraph), action("set_nodes", agent_node_config.RoleConfig), action("materialize_templates", sandbox_file_editor.EditManager), action("format_template", template_format.TemplateFormatter), action("initialize_guide", sandbox_guide_delivery.GuideDelivery), knows("is_step_mode", agent_node_config.NodeConfig).
        """
        ...



