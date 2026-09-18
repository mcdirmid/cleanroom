# sandbox_run_control_impl implementation component

imports: tool_provider, agent_file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, agent_node_config, template_format
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, guide step mode advancement, and verification checks for advance, submit, fail, blame, and check file tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not modify files on disk, parse syntax trees, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The run controller unconditionally installs the submit tool, fail tool, and check file tool for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured. Verification checks exposed by the run controller include the session verification checks from node config.

Evaluation of verification checks is cached alongside the edit manager file update revision. Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation. When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.

The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`. On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results. On subsequent executions, executing the advance tool updates verification results if outdated. Tool execution:

- Fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before advancing.

- Advances guide delivery and delivers the next step section when verification is passing and guide steps remain.

- Fails with a reminder to call the submit tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.

- Produces a response specifying a follow-up execution of the submit tool without a change summary and with reasoning text indicating that all guide steps are complete when verification is passing, no steps remain, and no workspace files were modified.

The submit tool is named `submit`, accepting an optional target parameter and a text *change summary* parameter, and shares a constant suppression key `submit`. Executing the submit tool updates verification results if outdated. In multi-target sessions, tool execution fails when the target parameter is omitted or does not match an open session target, reminding the agent to specify an open target. Tool execution fails when an in-session dependency of the target has not yet been submitted, reminding the agent that in-session dependencies must be submitted before dependent targets. Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call with reasoning text indicating that remaining guide steps must be completed before finishing. Tool execution fails when verification is failing, reminding the agent that the check file tool should be called first and specifying a follow-up execution of the check file tool with reasoning text indicating that verification results must be inspected before submitting. Tool execution fails when session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used. Tool execution fails if workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files. Tool execution marks the target as submitted, locks the target read-write files in the edit manager against modification, and produces a terminating response indicating that the session completed successfully when all session targets are resolved, or produces a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.

The fail tool is named `fail`, accepting an optional target parameter and a text *explanation* parameter. Executing the fail tool marks the target as failed, locks the target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response carrying the explanation when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.

The check file tool is named `check_file`, accepting an optional src parameter, and shares a constant suppression key `check_file`. Executing the check file tool updates verification results if outdated. When a src target is specified, executing the check file tool evaluates verification checks for that target. Tool execution:

- Reminds the agent that verification passed or failed and that no new information will be revealed by the tool call until session read-write files are updated when workspace files have not been updated since the previous check file tool execution.

- Specifies a follow-up execution of the view file tool on the session source file and reasoning text noting that verification passed and to advance or submit the session if correct, or noting that verification failed until files are updated, when workspace files have not been updated since the previous check file tool execution.

- Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.

- Produces a response presenting passing verification results using the session verification success message when configured or default passing verification results alongside sanitized check output when verification passes.

The blame tool is named `blame`, accepting an optional source target parameter, a file alias *blame target* parameter, and a text *explanation* parameter. In single-target sessions, the source target parameter defaults to the single target file, and the blame target parameter accepts the target parameter for backward compatibility. Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed. On successful blame tool execution, the response marks the submitted target of the blame as resolved, locks the submitted target read-write files in the edit manager against modification, and marks in-session dependent targets as blocked, producing a terminating response attributing defect feedback to the blame target owning node when no open targets remain, or producing a non-terminating response with a reminder listing remaining open target files formatted via the template formatter when open targets remain.
