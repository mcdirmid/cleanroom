# sandbox_run_control_impl implementation component

imports: tool_provider, agent_file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, agent_node_config, template_format, agent_config, dag_subgraph, sandbox
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, guide step mode advancement, and verification checks for advance, submit, fail, blame, check file, and get work tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not modify files on disk, parse syntax trees, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The run controller unconditionally installs the submit tool, fail tool, check file tool, and get work tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured. Verification checks exposed by the run controller include the session verification checks from node config.

Session targets are matched by alias, relative path, or unique filename against open session targets. When a target parameter is omitted, it defaults to:

- The single session read-write file or remaining unsubmitted target.

- The last read or written path when multiple unsubmitted read-write files exist and that path corresponds to an open session target.

Tool execution fails when a target parameter is omitted and cannot be defaulted, or when the specified target parameter does not match an open session target, reminding the agent to specify an open target.

Resolving a session target locks its declared read-write files in the edit manager against subsequent modification, and marks in-session dependent targets as blocked upon target failure or blame attribution. When blame, submit, or fail is successfully called on a submit target and other submit targets remain, resolving the target produces a non-terminating response with a reminder listing remaining submit targets left for the agent to handle formatted via the template formatter. When all session targets are resolved, resolving a target:

- Produces a terminating response indicating that the session completed successfully for submitted targets, carrying the explanation for failed targets, or attributing defect feedback to the blame target owning node for blamed targets, when mcp mode is inactive.

- Produces a non-terminating response with a reminder to call the get work tool when mcp mode is active.

Evaluation of verification checks is cached alongside the edit manager file update revision. Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation. When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.

The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`. On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results. On subsequent executions, executing the advance tool updates verification results if outdated.

Tool execution:

- Fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before advancing.

- Advances guide delivery and delivers the next step section when verification is passing and guide steps remain.

- Fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.

- Produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.

The submit tool is named `submit`, accepting a target parameter and a text *change summary* parameter, and shares a constant suppression key `submit`. Executing the submit tool updates verification results if outdated. Tool execution:

- Fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets.

- Fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing.

- Fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool targeting the submitted target with reasoning text indicating that verification results must be inspected before submitting.

- Fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.

- Fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.

- Marks the target as submitted and resolves the target.

The fail tool is named `fail`, accepting a target parameter and a text *explanation* parameter. Executing the fail tool marks the target as failed and resolves the target.

The blame tool is named `blame`, accepting a source target parameter, a file alias *blame target* parameter, and a text explanation parameter. Tool execution:

- Defaults the source target parameter to that session target when the blame target matches a configured blame target of an open session target.

- Defaults the blame target parameter to that target and the source target parameter to the session target configured with that blame target when the blame target parameter is omitted and the source target parameter matches a configured blame target.

- Defaults the source target parameter using session target defaulting rules when the source target parameter is omitted and cannot be inferred from the blame target.

- Fails if the blame target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed.

- Marks the blame target as attributed and resolves the source target on successful tool execution.

The check file tool is named `check_file`, accepting a path parameter (with src accepted as an alias), and shares a constant suppression key `check_file`. When the path parameter is omitted, the path parameter defaults using session target defaulting rules. Executing the check file tool updates verification results if outdated and evaluates verification checks for that target.

Tool execution:

- Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous check file tool execution.

- Specifies a follow-up execution of the view file tool on the session source file (resolving to the specified path target if a read-write file, the last accessed read-write file, or the primary session read-write file) and reasoning text noting that verification passed and to advance or submit the session if correct, or noting that verification failed until files are updated, when workspace files have not been updated since the previous check file tool execution.

- Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.

- Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.

The get work tool is named `get_work`, accepting an integer *max batch size* parameter. Tool execution:

- Fails when open session targets remain, reminding the agent that open targets must be resolved before requesting new work.

- Obtains dirty nodes from dag storage and dag subgraph, updating the active nodes and execution version on role config, when no open targets remain.

- Produces an idle response indicating that no dirty nodes are ready if no dirty nodes are ready for cleaning.

- Materializes startup templates on disk, constructs the task prompt from dirty node definitions, guide instructions, and incoming messages from dag storage formatted via the template formatter, and returns the rendered task prompt when ready dirty nodes are obtained.
