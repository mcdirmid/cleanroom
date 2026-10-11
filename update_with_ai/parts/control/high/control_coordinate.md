<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 406a0d0cf290
SPEC_QA_AUDIT: 2026-10-11T22:09:02Z
-->

# control_coordinate interface component

imports: agent_session, dag_storage, dag_subgraph, control_verification, control_work_scheduler, control_submit, control_attribution

## Purpose

The control_coordinate interface component defines the central session control coordinator facade for work discovery, verification over one target or every target, target submission, and defect attribution.

Complex coding sessions require a coherent execution control plane that unifies task discovery, verification evaluation, and outcome resolution into consistent operations. Without a central coordinator, individual tools redundantly track active nodes, desynchronize session state, and duplicate verification caching. The control_coordinate interface component coordinates active session nodes, provides verification across a specific file or all active work, resolves default target assignments, and dispatches scheduling, submission, and attribution operations.

**Out of scope:** The control_coordinate interface component does not implement conversational LLM prompt formats or manage terminal sockets; these are handled by other components.

**Delegated:** Task scheduling across directory scopes or execution subgraphs is delegated to control_work_scheduler; verification checking is delegated to control_verification; submission validation is delegated to control_submit; defect attribution is delegated to control_attribution; graph node tracking is delegated to dag_storage; subgraph modeling is delegated to dag_subgraph; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *target state* classifies an active target as *open*, *clean*, *failed*, or *attributed*.

A *control dispatch outcome* reports the unified result of a control action, carrying a *success* status, a diagnostic *message*, and *remaining open targets*.

An agent session's *session coordinator* maintains active targets and dispatches control operations.

The session coordinator tracks the active targets of the session with their target states and associated file aliases, and resolves a default target node when a target parameter is omitted, selecting the single open target or the most recently accessed open file.

The session coordinator dispatches work scheduling across either an execution subgraph or a directory scope, populating the active targets of the session.

The session coordinator dispatches verification checking, evaluating a specific target file when a target path is supplied or every open target when no target is supplied.

The session coordinator dispatches target submission, validating preconditions and change summary rules before marking targets clean, and dispatches blame attribution and task failure, routing defect feedback to culprits and recording failure diagnostics.
