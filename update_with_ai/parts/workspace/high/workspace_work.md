<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-06T22:55:00Z
CHANGE: new file
CODE_HASH: 473bd42798ae
-->

# workspace_work interface component

imports: agent_session, workspace_registry, control_work_scheduler, src_metadata

## Purpose

The workspace_work interface component defines data types and operational contracts for discovering ready and blocked tasks, evaluating in-scope dirtiness, and managing pending work queues within directory-scoped role workspaces.

Autonomous agents operating without subgraphs or full DAG models require accurate, directory-scoped work discovery to determine which targets need cleaning, which are blocked by upstream prerequisites, and when turns can terminate cleanly. Guessing work status or scanning files ad-hoc wastes context tokens, causes out-of-order execution, and results in premature turn termination. The workspace_work interface component establishes contracts for querying ready tasks using dynamic role precedence, inspecting pending work buffers, computing actionable next steps, and tracking pending targets across turns.

**Out of scope:** The workspace_work interface component does not commission workspace directories, transfer source files, or execute test commands; these are handled by other components.

**Delegated:** Role configuration lookups and path resolution are delegated to workspace_registry; topological dependency scheduling and dirtiness evaluation across directory scopes are delegated to control_work_scheduler; in-band source metadata extraction is delegated to src_metadata.

## Types and Behavior

A *work queue item* record encapsulates a pending task: a *target file*, a *role name*, a sequence of *dirtiness reasons*, a sequence of *dependency files*, an optional *blocked reason*, and an *is ready flag*.

A *work queue summary* record encapsulates the overall state of a directory scope: a sequence of *ready items*, a sequence of *blocked items*, and an *is clean flag*.

A session's *workspace work manager* evaluates and presents actionable work items for role workspaces.

The workspace work manager:

- Evaluates dirty targets and topological readiness across a specified directory scope, discovering ready and blocked work items according to dynamic role precedence without requiring a subgraph.

- Rejects new work discovery requests when uncompleted dirty work remains pending from a previous query in the role workspace, unless forced.

- Records ready targets into a local pending work buffer upon successful discovery, and clears the pending work buffer when all targets in scope evaluate clean.

- Formulates structured work queue summaries detailing ready targets, dirty reasons, prerequisite blockers, and actionable next steps for the active role.
