# sandbox_run_control_impl implementation component

imports: tool_provider, file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, node_config
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, guide step mode advancement, and verification checks for advance, finish, fail, blame, and run tests tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not modify files on disk, parse syntax trees, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The run controller unconditionally installs the finish tool, fail tool, and run tests tool for the agent session, installs the advance tool when guide step mode is active, and installs the blame tool when blame targets are configured. Verification checks exposed by the run controller include the session verification checks.

Evaluation of verification checks is cached alongside the edit manager file update revision. Verification checks are evaluated sequentially and results are cached whenever verification results are outdated, which occurs before initial evaluation and when workspace files have been updated since the previous evaluation. When workspace files have not been updated since the previous evaluation, verification check execution is omitted and the cached verification outcome is reused.

The advance tool is named `advance`, accepts no parameters, and shares a constant suppression key `advance`. On its first execution, the advance tool delivers the initial guide summary through guide delivery without updating verification results. On subsequent executions, executing the advance tool updates verification results if outdated. Tool execution:

- Fails when verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool.

- Advances guide delivery and delivers the next step section when verification is passing and guide steps remain.

- Fails with a reminder to call the finish tool with a change summary describing modifications when verification is passing, no steps remain, and workspace files were modified.

- Produces a response specifying a follow-up execution of the finish tool without a change summary when verification is passing, no steps remain, and no workspace files were modified.

The finish tool is named `finish`, accepting a text *change summary* parameter, and shares a constant suppression key `finish`. Executing the finish tool updates verification results if outdated. Tool execution fails in the following order when:

- Guide step mode is active and guide steps remain in guide delivery, reminding the agent that the advance tool must be called while guide steps remain and specifying the advance tool as a follow-up tool call.

- Verification is failing, reminding the agent that the run tests tool should be called first and specifying a follow-up execution of the run tests tool.

- Session feedback is present and no workspace files were modified, reminding the agent that workspace files must be modified to address feedback or that the fail tool must be used.

- Workspace files were modified and the change summary is omitted, reminding the agent that a change summary must be provided when completing the session after modifying workspace files.

- No workspace files were modified and the change summary is provided, reminding the agent that a change summary can only be provided when workspace files were modified.

Tool execution produces a terminating response indicating that the session completed successfully when verification is passing and all completion criteria are met.

The fail tool is named `fail`, accepting a text *explanation* parameter. Executing the fail tool produces a terminating response carrying the provided failure explanation.

The run tests tool is named `run_tests`, accepts no parameters, and shares a constant suppression key `run_tests`. Executing the run tests tool updates verification results if outdated. Tool execution:

- Fails when verification fails, presenting diagnostic feedback sanitized through the alias manager alongside any configured verification failure instructions.

- Produces a response presenting passing verification results when verification passes.

The blame tool is named `blame`, accepting a file alias *blame target* parameter and a text *explanation* parameter. Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed. On success, executing the blame tool produces a terminating response attributing defect feedback to the owning dependency node.
