<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Restore cleaned metadata and tighten purpose rationale to two paragraphs
CODE_HASH: d17c245878e4
-->

# topological_order_ext external component

## Purpose

The topological_order_ext external component defines deterministic dependency-first ordering knowledge for dependency graphs whose edges are already declared.

Ordering a set of declared items requires a total order that respects every dependency edge, reproduces identically across runs, and remains defined when the graph contains a cycle or two items are mutually independent. Leaving those details to unstated knowledge makes traversal order, tie-breaking, and cycle behavior accidental, so two implementations of the same specification emit different sequences for the same dependency map.

The topological_order_ext external component states the ordering rules once, covering dependency-first traversal over the transitive closure, lexical tie-breaking, and explicit cycle behavior, so every component that needs an order grounds on a stated algorithm instead of inventing one.

**Out of scope:** The topological_order_ext external component does not discover dependencies, evaluate dirtiness, or schedule work; these are handled by other components.

## Grounding Gaps Covered

The topological_order_ext component provides ordering knowledge for computing a deterministic dependency-first order over declared items.

Grounding gaps covered include:

- Dependency-first ordering: An item is emitted after every item it depends on, directly or transitively, so the sequence is a linear extension of the dependency relation rather than an ordering of direct edges alone.

- Deterministic tie-breaking: Items that no dependency edge orders relative to one another are emitted in lexical order of their names, and the dependencies of an item are likewise traversed in lexical order, so the emitted sequence is a pure function of the item set and the dependency mapping.

- Transitive closure over declared items: A dependency naming an item that is not in the input set is ignored, so an undeclared dependency never creates a gap or a placeholder in the emitted sequence.

- Cycle behavior: A dependency edge that closes a cycle is not followed. Ordering terminates, each declared item is emitted exactly once, and no error is raised, so a caller that needs cycles reported detects them separately rather than relying on the order.

- Single emission: Every declared item appears exactly once, whether it declares dependencies, is declared as a dependency, or neither.
