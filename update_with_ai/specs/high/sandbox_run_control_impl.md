# sandbox_run_control_impl implementation component

imports: tool_provider, file_alias, dag_storage, sandbox_file_editor, sandbox_guide_delivery, node_config
implements: sandbox_run_control

## Purpose

The sandbox_run_control_impl implementation component realizes self-contained outcome evaluation, guide step mode advancement, and verification checks for advance, fail, and blame tools.

Autonomous agents reaching task completion require strict verification enforcement to ensure dirty files are documented, progressive milestones are completed, and broken builds are caught before terminating a turn. The sandbox_run_control_impl implementation component coordinates milestone progression with guide delivery, inspects edit manager modification state, evaluates installed verification checks, and validates blame targets, converting outcome decisions into structured tool responses.

**Out of scope:** The sandbox_run_control_impl implementation component does not modify files on disk, parse syntax trees, or compute topological dependency schedules; these are handled by other components.

## Types and Behavior

The run controller unconditionally installs the advance tool and fail tool into the tool manager for the agent session, obtaining configured blame targets and verification checks from the node config and installing the blame tool only when blame targets are configured. Verification checks exposed by the run controller include the session verification checks from node config.

The advance tool is named `advance` and accepts a text *change summary* parameter that must be omitted while guide steps remain and is required only when concluding the session after modifying workspace files. Executing the advance tool coordinates self-contained advancement:

- A call to the advance tool can be injected when an agent session starts when using step mode to deliver initial step content, executing without requiring a change summary.
 
- When guide step mode is on and steps remain in guide delivery, tool execution fails if a change summary is provided, and reminds the agent that a change summary can only be provided when completing the session after seeing all guide steps.

- When no file has changed, tool execution fails if a change summary is provided, and reminds the agent that a change summary can only be provided when workspace files were modified.

- If workspace files were modified and either guide step mode is not on or no steps remain in guide delivery, tool execution fails if the change summary is not provided, and reminds the agent that a change summary must be provided when completing the session after modifying workspace files.

- Verification checks execute as long as the change summary is set correctly, unless the previous advance call failed verification and no workspace files have been updated since.
 
- When verification checks execute and any verification check fails, tool execution fails with diagnostic feedback sanitized through the alias manager, and the advance tool caches the failure output alongside the current file update revision from the edit manager.

- When the advance tool is called after a previous advance call that failed verification and no workspace files have been updated since that failure as indicated by the edit manager's file update revision, tool execution fails without re-executing verification checks, serving the cached output from the previous failed verification and reminding the agent that verification failed previously and workspace files must be updated before advancing again.
 
- When guide step mode is on, tool execution always presents the guide summary from node config whether execution fails or succeeds.

The fail tool is named `fail`, accepting a text *explanation* parameter. Executing the fail tool produces a terminating response carrying the provided failure explanation.

The blame tool is named `blame`, accepting a file alias *blame target* parameter and a text *explanation* parameter. Executing the blame tool fails if the target does not match any configured blame target, providing an error response listing the available blame targets and reminding the agent that only upstream files configured as blame targets can be blamed. On success, executing the blame tool produces a terminating response attributing defect feedback to the owning dependency node.
