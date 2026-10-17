<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: eef26cd62e8b
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# work_scheduler interface component

imports: session, dag_storage, subgraph

## Purpose

The work_scheduler interface component defines work discovery over subgraphs and directory scopes, role tier depth scheduling, and task prompt synthesis for dirty targets.

Engineering workflows require discovering work across both focused execution subgraphs and broad directory scopes without hardcoding role lifecycle phases. When role ordering is hardcoded, new lifecycle phases are skipped or scheduled out of sequence, causing downstream steps to run before upstream contracts are established. The work_scheduler interface component schedules ready dirty nodes using dynamic topological role precedence derived from declared role dependencies, and synthesizes task prompts incorporating upstream feedback.

**Out of scope:** The work_scheduler interface component does not execute compilers, modify source code, or submit nodes; these are handled by other components.

**Delegated:** Graph storage access is delegated to dag_storage; execution subgraph structures are delegated to subgraph; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

A *scheduled task* identifies a ready target node, supplying its *task prompt*, declared *upstream dependency paths*, and any unresolved *defect feedback* messages.

A *work schedule* contains an ordered sequence of scheduled tasks ready for processing.

An agent session's *work scheduler* determines ready tasks and synthesizes work instructions.

The work scheduler discovers ready dirty nodes within a specified target subgraph or across a specified directory scope.

The work scheduler orders candidate nodes by role tier depth, so that upstream roles are scheduled before downstream roles without naming any role.

The work scheduler evaluates the readiness of a candidate node by checking that every direct non-silent upstream dependency in graph storage is clean.

The work scheduler synthesizes scheduled tasks by loading role guides, formatting task instructions, listing declared dependency paths, deriving companion grounding specifications based on upstream role dependencies, and appending the unaddressed feedback messages recorded on the target node.
