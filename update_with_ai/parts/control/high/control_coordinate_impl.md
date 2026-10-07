<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 5394f5d244d6
-->

# control_coordinate_impl implementation component

imports: agent_session, dag_storage, control_verification, control_work_scheduler, control_submit, control_attribution, agent_node_config, agent_file_alias, dag_subgraph
implements: control_coordinate

## Purpose

The control_coordinate_impl implementation component realizes unified session dispatch, target state tracking, default target resolution, and multi-mode verification and scheduling orchestration.

Orchestrating multi-node workflows requires maintaining accurate node lifecycle state across successive tool executions so that dependent nodes are submitted in valid topological order and default targets resolve predictably. The control_coordinate_impl implementation component coordinates session node states, resolves file aliases to graph nodes, routes check files calls to single targets or all active work, schedules new work batches from subgraphs or directory scopes, and delegates submission and attribution logic to specialized coordinators.

**Out of scope:** The control_coordinate_impl implementation component does not implement JSON-RPC protocols or format terminal UI widgets; these are handled by other components.

**Delegated:** Verification check execution is delegated to control_verification. Work scheduling and prompt generation are delegated to control_work_scheduler. Submission gating is delegated to control_submit. Defect attribution and failure handling are delegated to control_attribution.

## Types and Behavior

The session coordinator implements session coordination for the session.

When coordinating active work:

- The session coordinator maintains registered session nodes, mapping each node to its file alias and current target state.

- When resolving a default target, the session coordinator selects the sole open target if exactly one remains, or selects the target corresponding to the most recently modified open file when multiple targets are open.

- When dispatching get work, the session coordinator invokes the work scheduler using either the provided subgraph or directory scope, registers newly scheduled nodes as open targets, and returns the synthesized work schedule.

- When dispatching check files, the session coordinator evaluates verification for the specified target file if provided, or evaluates verification across all open session targets if no target is specified, returning sanitized diagnostic results and indicating whether cached results were reused.

- When dispatching submit, the session coordinator delegates validation and resolution to the submission coordinator, updating the target state to clean upon success.

- When dispatching blame or fail, the session coordinator delegates defect attribution or failure logging to the attribution coordinator, updating the target state to attributed or failed and marking any in-batch dependents as failed.
