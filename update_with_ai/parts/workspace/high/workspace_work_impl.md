<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: a26a475c8f28
-->

# workspace_work_impl implementation component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata
implements: workspace_work

## Purpose

The workspace_work_impl implementation component realizes work queue discovery across directory scopes using dynamic role precedence, pending work tracking, and actionable diagnostic generation.

Guiding autonomous agents through multi-step pipeline tasks requires distinguishing ready targets from targets blocked on upstream artifacts while enforcing completion of pending work before starting new tasks. Without strict queue tracking, agents jump between disconnected files or exit before completing verification. The workspace_work_impl implementation component invokes directory-scoped work scheduling, filters candidates by active role, evaluates pending target dirtiness against local and main workspaces, persists pending target state in `.cleanroom_pending_work.json`, and generates structured task outputs with actionable guidance.

**Out of scope:** The workspace_work_impl implementation component does not commission workspace directories, transfer source files, or execute test commands; these are handled by other components.

**Delegated:** Role configuration lookups and path resolution are delegated to workspace_registry; topological dependency scheduling and dirtiness evaluation across directory scopes are delegated to control_work_scheduler; in-band source metadata extraction is delegated to src_metadata.

## Types and Behavior

The workspace work manager discovers work items within a designated directory scope.

When managing pending target state:

- The work manager records assigned target paths to `.cleanroom_pending_work.json`.

- The work manager removes a resolved target path from `.cleanroom_pending_work.json` when submitted or blamed.

- The work manager evaluates whether a pending target remains dirty by checking in-band source metadata across local and canonical repositories.

When evaluating work in a role workspace:

- The work manager checks whether a pending work buffer file exists at `.cleanroom_pending_work.json`. If pending targets exist, the manager re-evaluates each target's dirty status using in-band metadata. If any target remains dirty and force is false, work discovery aborts, returning an error directing the agent to complete or blame the pending target.

- If all previously pending targets are clean, the manager clears the pending work buffer file.

- The work manager schedules work for the directory scope using the work scheduler without providing a subgraph, scanning units in scope, checking dependency dirtiness, and sorting candidate tasks by dynamic role precedence.

- The work manager partitions candidate tasks into ready items whose forward dependencies are clean, and blocked items whose prerequisites remain dirty.

- If ready items exist and a role workspace is active, the manager records the ready target file paths into the pending work buffer.

- The work manager resolves companion upstream specification contract files and interface definitions for candidate targets using dynamic role definitions from workspace_registry, avoiding peer implementation file leakage.

- The work manager resolves cross-unit dependencies by filtering out silent cross-role dependencies and expanding star-role specification contracts dynamically defined in workspace_registry.

- The work manager enforces fail-loud resolution for unknown roles or unmatched paths, raising explicit exceptions without synthetic fallbacks.

- The work manager compiles the results into a work queue summary detailing ready tasks, dirty reasons, dependency paths, companion contract files, blocked causes, and role-specific instructions.
