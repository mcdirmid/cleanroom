<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:47Z
LAST_CHANGED: 2026-10-10T19:00:00Z
CHANGE: track dirtiness through implicit role deps and star role changes
CODE_HASH: 137092e219c3
SPEC_QA_AUDIT: 2026-10-15T17:42:47Z
-->

# work interface component

imports: session, cleanroom_files_ext

## Purpose

The work interface component defines data types and operational contracts for discovering ready and blocked tasks, evaluating in-scope dirtiness, and managing pending work queues within directory-scoped role workspaces.

Autonomous agents operating without subgraphs or full DAG models require accurate, directory-scoped work discovery to determine which targets need cleaning, which are blocked by upstream prerequisites, and when turns can terminate cleanly. Guessing work status or scanning files ad-hoc wastes context tokens, causes out-of-order execution, and results in premature turn termination. The work interface component establishes contracts for querying ready tasks by role tier depth, inspecting pending work buffers, computing actionable next steps, and tracking pending targets across turns.

**Out of scope:** The work interface component does not commission workspace directories, transfer source files, or execute test commands; these are handled by other components.

**Delegated:** Session lifecycle scoping is delegated to agent_session; workspace file conventions are delegated to cleanroom_files_ext.

## Types and Behavior

A *work queue item* record encapsulates a pending task, carrying a *target file*, a *role name*, *dirtiness reasons*, *dependency files*, companion *contract files*, *blocked reasons*, and an *is ready* status indicating whether the prerequisites of the task are satisfied.

A *work queue summary* record encapsulates the overall state of a directory scope, carrying *ready items*, *blocked items*, an *is clean* status indicating whether every unit in scope evaluates clean, and an optional *remaining ready count* indicating unpresented ready tasks beyond the current batch.

An agent session's *workspace work manager* evaluates and presents actionable work items for role workspaces.

The workspace work manager:

- Evaluates dirty targets and topological readiness across a specified directory scope, discovering ready and blocked work items by role tier depth without requiring a subgraph, bounding presented ready items when a batch size is specified, treating feedback role dependencies and star role dependencies as implicit role dependencies for dirty tracking, evaluating a target as dirty when any star role dependency changes, and materializing starter templates through graph storage for missing ready target files.

- Resolves the companion upstream specification contracts and interface definitions of target units from role definitions, automatically inspecting and including companion interface contracts without the _impl suffix for any unit ending in _impl, guiding agent implementation and verification.

- Filters cross-unit dependencies by configured star-role dependencies and silent cross-role dependencies, suppressing the peer implementation files that match a silent cross-role dependency and expanding star-role specification contracts.

- Enforces strict role resolution without synthetic fallbacks, failing loudly when an unknown role or an unrecognized file pattern is encountered.

- Rejects a new work discovery request while uncompleted dirty work remains pending from a previous query in the role workspace, unless the request is forced.

- Manages pending target tracking by recording assigned targets into a local pending work buffer file, removing submitted targets, and checking target dirtiness, materializing starter templates through graph storage when a missing target file belongs to a role with source patterns and upstream dependencies.

- Clears the pending work buffer file when all targets in scope evaluate clean.

- Formulates structured work queue summaries detailing ready targets, dirty reasons, prerequisite blockers, and actionable next steps for the active role.
