<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 1ab4b48f3086
-->

# control_work_scheduler interface component

imports: agent_session, dag_storage, dag_subgraph, agent_node_config

## Purpose

The control_work_scheduler interface component defines dual-mode work discovery, dynamic role precedence scheduling, and task prompt synthesis for dirty targets.

Engineering workflows require discovering work across both focused execution subgraphs and broad directory scopes without hardcoding role lifecycle phases. When role ordering is hardcoded, new lifecycle phases are skipped or scheduled out of sequence, causing downstream steps to run before upstream contracts are established. The control_work_scheduler interface component schedules ready dirty nodes using dynamic topological role precedence derived from declared role dependencies, and synthesizes task prompts incorporating upstream feedback.

**Out of scope:** The control_work_scheduler interface component does not execute compilers, modify source code, or submit nodes; these are handled by other components.

## Types and Behavior

A *scheduled task* identifies a ready target node, supplying its *task prompt*, declared *upstream dependency paths*, and any unresolved *defect feedback* messages.

A *work schedule* contains an ordered sequence of scheduled tasks ready for processing.

A session's *work scheduler* determines ready tasks and synthesizes work instructions.

The work scheduler:

- Discovers ready dirty nodes within a specified target subgraph or across a specified directory scope.

- Orders candidate nodes by dynamic role precedence, ranking roles according to the topological depth of declared role dependencies so that upstream roles are scheduled before downstream roles without hardcoded role identifiers.

- Evaluates readiness of candidate nodes by checking that all direct non-silent upstream dependencies in graph storage are clean.

- Synthesizes scheduled tasks by loading role guides, formatting task instructions, listing declared dependency paths, and appending unaddressed feedback messages recorded on the target node.
