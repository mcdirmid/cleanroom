<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 94931d97b2a3
-->

# control_coordinate interface component

imports: agent_session, dag_storage, control_verification, control_work_scheduler, control_submit, control_attribution, agent_node_config, agent_file_alias

## Purpose

The control_coordinate interface component defines the central session control coordinator facade for work discovery, dual-mode verification, target submission, and defect attribution.

Complex coding sessions require a coherent execution control plane that unifies task discovery, verification evaluation, and outcome resolution into consistent operations. Without a central coordinator, individual tools redundantly track active nodes, desynchronize session state, and duplicate verification caching. The control_coordinate interface component coordinates active session nodes, provides dual-mode verification across specific files or all active work, resolves default target assignments, and dispatches scheduling, submission, and attribution operations.

**Out of scope:** The control_coordinate interface component does not implement conversational LLM prompt formats or manage terminal sockets; these are handled by other components.

## Types and Behavior

A *target state* classifies an active target as *open*, *clean*, *failed*, or *attributed*.

A *control dispatch outcome* reports the unified result of a control action, carrying a boolean *success* status, a diagnostic *message*, and an optional sequence of *remaining open targets*.

A session's *session coordinator* maintains active targets and dispatches control operations.

The session coordinator:

- Tracks active targets in the session, their target states, and their associated file aliases.

- Resolves a default target node when a target parameter is omitted, selecting the single open target or the most recently accessed open file.

- Dispatches work scheduling across either an execution subgraph or a directory scope, populating the active targets of the session.

- Dispatches verification checking in dual mode: evaluating a specific target file when a target path is supplied, or evaluating all open targets when invoked without a target argument.

- Dispatches target submission, validating preconditions and change summary rules before marking targets clean.

- Dispatches blame attribution and task failure, routing defect feedback to culprits and recording failure diagnostics.
