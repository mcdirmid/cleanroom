# sandbox_run_control_impl implementation component

imports: tool_provider, file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, node_config
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, progressive step advancement, and verification checks for advance, fail, and blame tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not modify files on disk, parse syntax trees, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The run controller unconditionally installs the advance tool and fail tool into the tool manager for the agent session, obtaining configured blame targets from the node config in node_config and installing the blame tool only when blame targets are configured. Verification checks installed on the run controller are recorded in sequence.

The advance tool is named `advance` and accepts a text *change summary* parameter. Executing the advance tool coordinates self-contained advancement:

- A call to the advance tool can be injected when an agent session starts when using step mode to deliver initial step content, executing without requiring a change summary.

- When progressive guide delivery is configured and steps remain in guide delivery, the advance tool advances to the next step section and returns its content as a non-terminating response.

- When no steps remain or guide delivery is not configured, the advance tool queries the edit manager to check whether workspace file modifications occurred during the session. If modifications occurred, execution fails if the change summary is empty.

- If change summary requirements are satisfied, the advance tool executes each installed verification check in order. If any verification check fails, execution fails with the diagnostic feedback produced by the check.

- If no files were modified, no verification checks were installed, and no change summary was provided, executing the advance tool fails.

- When all verification checks pass, executing the advance tool produces a terminating response indicating completion.

The fail tool is named `fail`, accepting a text *explanation* parameter. Executing the fail tool produces a terminating response carrying the provided failure explanation.

The blame tool is named `blame`, accepting a file alias *blame target* parameter and a text *explanation* parameter. Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets. On success, executing the blame tool produces a terminating response attributing defect feedback to the owning dependency node.
