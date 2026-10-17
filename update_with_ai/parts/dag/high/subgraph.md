<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Define role precedence as a stated rule and restructure the subgraph operation list
CODE_HASH: a386d70ff0a4
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# subgraph interface component

imports: dag_storage

## Purpose

The subgraph interface component provides an active subgraph view over graph storage to query topological order, evaluate completion status, and batch ready dirty nodes for execution schedulers.

Coordinating multi-node agent workflows requires inspecting graph progress, identifying independent tasks that can be scheduled concurrently, and isolating reachable dependencies from unrelated workspace targets. Direct queries against unstructured graph storage force orchestrators to re-implement graph traversal algorithms and duplicate dependency validation, risking race conditions and inconsistent execution schedules. The subgraph interface component establishes a query boundary over graph storage that maintains an active target subgraph, isolates reachable dependencies, and delivers topologically sorted, ready-to-clean node batches to execution runners.

**Out of scope:** The subgraph interface component does not clean individual nodes, deliver messages, or execute agent turn loops; these are handled by other components.

## Types and Behavior

A *role tier depth* is a role's position in the declared role dependency order, where a role with no role dependency has a depth of zero and any other role has a depth one greater than the deepest role it depends on. A role tier depth makes upstream roles precede downstream roles without naming any role.

A system's *dag subgraph* models an active execution subgraph rooted at a target node in dag storage, and maintains the reachable nodes of that subgraph in dependency-first topological order. Role addresses follow the canonical syntax `//<scope>/parts/<part>:<role>` or unqualified `:role`. Nodes that no dependency orders relative to one another are ordered by role tier depth first, evaluating alphabetical role precedence using the unqualified role identifier following the final colon delimiter, and by unit address second.

The dag subgraph also reports whether the target subgraph is *complete*, which holds if, but only if, every reachable node in the target subgraph is clean in dag storage.

The dag subgraph provides the *next ready batch* of dirty nodes to clean. The next ready batch holds uncleaned dirty nodes whose dependencies in the target subgraph are clean in dag storage or present in the same batch, selected from the earliest ready dirty node in topological order and grouped by role address within the batch. The next ready batch is an empty sequence when no dirty node in the target subgraph has all of its dependencies in the target subgraph clean in dag storage.

The dag subgraph can *record visit* for a batch of nodes being cleaned, advancing the visit count of each node in the batch and failing when a node exceeds a configured visit limit.
