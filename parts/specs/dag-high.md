# dag

imports: dag_storage (graph + messages), dag_clean_logic (cleaning)
terms (from dag_storage): node, dependency, pending message, subgraph, reverse dependency
terms (from dag_clean_logic): dirty, cleaning, change message, feedback message

## Purpose

Cleans every dirty node in the subgraph rooted at a target node, in topological order, routing change messages to reverse dependencies and feedback messages to specific dependencies, until no dirty nodes remain.

## Contract

**Inputs**

- Per cleaning request: a target node, the root of the subgraph to clean.

**Operations**

- Request cleaning of the subgraph rooted at a target node.

**Guarantees**

- Cleaning produces no direct output; messages are routed to node stores via dag_storage.
- Cleaning can re-dirty nodes (message delivery), so a node may be cleaned multiple times; feedback re-dirties previously cleaned nodes, processed in subsequent iterations.
- Nodes outside the subgraph may receive messages and become dirty, but are not cleaned until a subgraph containing them is cleaned.
- Cleaning is topological: the sort is computed once and fixed for the operation; a node is cleaned only while none of its dependencies are dirty; dirtiness is re-evaluated for all nodes after each cleaning; iteration stops when no node in the sort is dirty.
- Each node's cleaning is atomic.
- Cleaning always terminates, bounded by a single total bound on clean operations.
- All state is per-run; no state persists across restarts.
- Failure — each leaves the offending node's messages unchanged and halts cleaning:
  - a node's cleaning fails;
  - message delivery would otherwise continue cleaning without bound;
  - feedback targets a node outside the subgraph (feedback is delivered only within the subgraph).
- A graph cycle signals failure, leaving state unchanged.

**Assumptions**

- The target node exists in the graph.
- The graph topology does not change during cleaning.
- No concurrent cleaning operations are initiated.
- No node receives a message while it is being cleaned.

## Non-concerns

- Cycle detection: the algorithm used to detect cycles is unspecified.
