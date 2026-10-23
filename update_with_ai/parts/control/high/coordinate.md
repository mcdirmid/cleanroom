# coordinate interface component

imports: session, dag_storage, subgraph, verification, work_scheduler, submit, attribution

## Purpose

The coordinate interface component defines the central session control coordinator facade for work discovery, verification over one target or every target, target submission, and defect attribution.

Complex coding sessions require a coherent execution control plane that unifies task discovery, verification evaluation, and outcome resolution into consistent operations. Without a central coordinator, individual tools redundantly track active nodes, desynchronize session state, and duplicate verification caching. The coordinate interface component coordinates active session nodes, provides verification across a specific file or all active work, resolves default target assignments, and dispatches scheduling, submission, and attribution operations.

**Out of scope:** The coordinate interface component does not implement conversational LLM prompt formats or manage terminal sockets; these are handled by other components.

**Delegated:** Task scheduling across directory scopes or execution subgraphs is delegated to work_scheduler; verification checking is delegated to verification; submission validation is delegated to submit; defect attribution is delegated to attribution; graph node tracking is delegated to dag_storage; subgraph modeling is delegated to subgraph; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *target state* classifies an active target as *open*, *clean*, *failed*, or *attributed*.

A *control dispatch outcome* reports the unified result of a control action, carrying a *success* status, a diagnostic *message*, and *remaining open targets*.

An agent session's *session coordinator* maintains active targets and dispatches control operations.

The session coordinator tracks the active targets of the session with their target states and associated file aliases, excluding ephemeral root session targets (such as //session:target) from persistent graph registration, and resolves a default target node when a target parameter is omitted, selecting the single open target or the most recently accessed open file.

The session coordinator dispatches work scheduling across either an execution subgraph or a directory scope, materializing starter templates through graph storage for newly dirtied scheduled task nodes whose target files do not exist on disk, and populating the active targets of the session.

The session coordinator dispatches verification checking, evaluating a specific target file when a target path is supplied or every open target when no target is supplied.

The session coordinator dispatches target submission, validating preconditions and change summary rules before marking targets clean, and dispatches blame attribution and task failure, routing defect feedback to culprits and recording failure diagnostics.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
