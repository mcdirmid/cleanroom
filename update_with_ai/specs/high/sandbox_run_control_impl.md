# sandbox_run_control_impl implementation component

imports: tool_provider, file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, node_config
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, guide step mode advancement, and verification checks for advance, fail, and blame tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not modify files on disk, parse syntax trees, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The run controller unconditionally installs the finish tool and fail tool into the tool manager for the agent session, installs the advance tool only when guide step mode is active, and obtains configured blame targets and verification checks from the node config, installing the blame tool only when blame targets are configured. Verification checks exposed by the run controller include the session verification checks from node config.

Evaluation of verification checks is cached alongside the edit manager file update revision. Verification check execution is omitted and the cached result is reused whenever workspace files have not been updated since the previous evaluation as indicated by the file update revision. When the previous evaluation failed and workspace files have not been updated since, tool execution fails with the cached diagnostic output, reminding the agent that workspace files must be updated before proceeding.

The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`. The advance tool presents the guide summary from node config whether execution fails or succeeds. Executing the advance tool coordinates self-contained guide progression:

- Passing verification advances guide delivery and delivers the next step section when guide steps remain.

- Failing verification halts progression and reports diagnostic feedback sanitized through the alias manager when guide steps remain.

- When no steps remain and workspace files were modified, passing verification fails tool execution with a reminder to call the finish tool with a change summary describing modifications.

- When no steps remain and no workspace files were modified, passing verification produces a response specifying a follow-up execution of the finish tool without a change summary.

- Failing verification reports sanitized diagnostic feedback when no steps remain.

The finish tool is named `finish`, accepting a text *change summary* parameter, and shares a constant suppression key `finish`. Executing the finish tool evaluates session completion criteria:

- Tool execution fails when guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call.

- Tool execution fails if workspace files were modified and the change summary is omitted, and reminds the agent that a change summary must be provided when completing the session after modifying workspace files.

- Tool execution fails if no workspace files were modified and the change summary is provided, and reminds the agent that a change summary can only be provided when workspace files were modified.

- Tool execution evaluates verification checks, failing with diagnostic feedback sanitized through the alias manager when any verification check fails.

- Passing verification produces a terminating response indicating that the session completed successfully.

The fail tool is named `fail`, accepting a text *explanation* parameter. Executing the fail tool produces a terminating response carrying the provided failure explanation.

The blame tool is named `blame`, accepting a file alias *blame target* parameter and a text *explanation* parameter. Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed. On success, executing the blame tool produces a terminating response attributing defect feedback to the owning dependency node.
