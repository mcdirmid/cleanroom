# coordinate_impl implementation component

imports: session, dag_storage, verification, work_scheduler, submit, attribution, node_config, file_alias, subgraph
implements: coordinate

## Purpose

The coordinate_impl implementation component realizes unified session dispatch, target state tracking, default target resolution, and multi-mode verification and scheduling orchestration.

Orchestrating multi-node workflows requires maintaining accurate node lifecycle state across successive tool executions so that dependent nodes are submitted in valid topological order and default targets resolve predictably. The coordinate_impl implementation component coordinates session node states, resolves file aliases to graph nodes, routes check files calls to single targets or all active work, schedules new work batches from subgraphs or directory scopes, and delegates submission and attribution logic to specialized coordinators.

**Out of scope:** The coordinate_impl implementation component does not implement JSON-RPC protocols or format terminal UI widgets; these are handled by other components.

**Delegated:** Verification check execution is delegated to verification. Work scheduling and prompt generation are delegated to work_scheduler. Submission gating is delegated to submit. Defect attribution and failure handling are delegated to attribution.

## Types and Behavior

The session coordinator implements session coordination for an agent session.

The session coordinator maintains registered session nodes, mapping each node to its file alias and current target state.

The session coordinator coordinates active work.

The session coordinator:

- Resolves a default target by selecting the sole open target when exactly one remains, or by selecting the target corresponding to the most recently modified open file when multiple targets are open.

- Resolves file aliases to registered session nodes via exact match, path suffix match, or role-compatible source file proxy match, ensuring file proxies for distinct roles do not cross-match.

- Dispatches get work by invoking the work scheduler with either the provided subgraph or directory scope, registering newly scheduled nodes as open targets, updating the sequence of active nodes on role config, and returning the synthesized work schedule.

- Dispatches check files by evaluating verification for the specified target file when provided, falling back to the single open target if unambiguous, or for all open session targets when no target is specified, returning sanitized diagnostic results and indicating whether cached results were reused.

- Dispatches submit by delegating validation and resolution to the submission coordinator, updating the target state to clean upon success.

- Dispatches blame by resolving blame targets against upstream configured blame targets or session aliases, guarding against self-blame, registering the attributed upstream node, delegating defect attribution to the attribution coordinator, updating the target state to attributed, and marking any in-batch dependents as failed.

- Dispatches fail by delegating failure logging to the attribution coordinator, updating the target state to failed, and marking any in-batch dependents as failed.

- Formats user-facing node aliases using source file paths or configured file patterns instead of exposing internal graph node target addresses.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-09T21:29:23Z
CHANGE: Synchronize active nodes sequence on role config during get work dispatch
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
