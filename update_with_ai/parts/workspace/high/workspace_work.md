<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T15:45:00Z
CHANGE: clarify starter template materialization for regenerable roles on check
CODE_HASH: 7405c91a686a
-->

# workspace_work interface component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata, dag_storage

## Purpose

The workspace_work interface component defines data types and operational contracts for discovering ready and blocked tasks, evaluating in-scope dirtiness, and managing pending work queues within directory-scoped role workspaces.

Autonomous agents operating without subgraphs or full DAG models require accurate, directory-scoped work discovery to determine which targets need cleaning, which are blocked by upstream prerequisites, and when turns can terminate cleanly. Guessing work status or scanning files ad-hoc wastes context tokens, causes out-of-order execution, and results in premature turn termination. The workspace_work interface component establishes contracts for querying ready tasks using dynamic role precedence, inspecting pending work buffers, computing actionable next steps, and tracking pending targets across turns.

**Out of scope:** The workspace_work interface component does not commission workspace directories, transfer source files, or execute test commands; these are handled by other components.

**Delegated:** Role configuration lookups and path resolution are delegated to workspace_registry; topological dependency scheduling and dirtiness evaluation across directory scopes are delegated to control_work_scheduler; in-band source metadata extraction is delegated to src_metadata; starter template materialization is delegated to dag_storage.

## Types and Behavior

A *work queue item* record encapsulates a pending task: a *target file*, a *role name*, a sequence of *dirtiness reasons*, a sequence of *dependency files*, a sequence of companion *contract files*, an optional *blocked reason*, and an *is ready flag*.

A *work queue summary* record encapsulates the overall state of a directory scope: a sequence of *ready items*, a sequence of *blocked items*, and an *is clean flag*.

A session's *workspace work manager* evaluates and presents actionable work items for role workspaces.

The workspace work manager:

- Evaluates dirty targets and topological readiness across a specified directory scope, discovering ready and blocked work items according to dynamic role precedence without requiring a subgraph, materializing starter templates via graph storage for missing ready target files.

- Resolves companion upstream specification contracts and interface definitions for target units from role definitions to guide agent implementation and verification.

- Filters cross-unit dependencies based on configured star-role dependencies and silent cross-role dependencies, suppressing peer implementation files matching silent cross-role dependencies and expanding star-role specification contracts.

- Enforces strict role resolution without synthetic fallbacks, failing loudly when unknown roles or unrecognized file patterns are encountered.

- Rejects new work discovery requests when uncompleted dirty work remains pending from a previous query in the role workspace, unless forced.

- Manages pending target tracking by recording assigned targets into a local pending work buffer, removing submitted targets, and checking target dirtiness, materializing starter templates via graph storage when checking missing target files for roles with source patterns and upstream dependencies.

- Clears the pending work buffer when all targets in scope evaluate clean.

- Formulates structured work queue summaries detailing ready targets, dirty reasons, prerequisite blockers, and actionable next steps for the active role.
