# bazel_graph_storage

imports: dag_storage (contract fulfilled with Bazel workspace data), sandbox (node definitions)
terms (from dag_storage): node, message, pending message, dependency, propagating dependency, reverse dependency, subgraph
terms (from sandbox): blame target, template, guide, step mode
terms (owned): node definition, package directory, silent dependency, star dependency

## Purpose

Provides Bazel-workspace-backed storage and graph access for the agent build: node dependencies, known reverse dependencies, pending messages, and per-node definitions. The dag_storage contract holds.

## Terms

- Node definition: the agent prompt and sandbox configuration declared by a node's target — file mappings, readable and writable paths, blame targets, the search result limit, the templates, and the guide.
- Package directory: the directory containing a node's BUILD file; also where the node's messages are stored.
- Silent dependency: a dependency a node declares as silent; a silent dependency is a dependency (cleaned before the declaring node) whose changes do not propagate to the declaring node.
- Star dependency: a dependency a node declares as a star dependency; a star dependency is a dependency (cleaned before the declaring node) whose declared source, and the declared source of every node reachable from it through star dependencies (never through non-star dependencies or silent dependencies), are readable by the declaring node.

## Contract

**Inputs**

- The workspace root (or an equivalent graph source), configured.
- Per query: a node ID (a valid Bazel target label).

**Operations**

- Perform the dag_storage operations: read pending messages, add messages, clear a node's pending messages, delete a node's data, retrieve dependencies, retrieve known reverse dependencies.
- Query a node's definition.
- Query a node's package directory.

**Guarantees**

- The dag_storage guarantees hold.
- A node's dependencies are the targets it declares, plus the guide node, which is cleaned before the node. The guide's readable and delivery treatment follows the step-mode flag: when step mode is disabled the guide is readable; when step mode is enabled the guide is not readable and its content reaches the agent only through the advance operation (per sandbox).
- A node's propagating dependencies are its declared dependencies, excluding its silent dependencies; retrieving a node's dependencies records the node as a reverse dependency of each declared dependency that is not silent, and of no silent dependency.
- Queries do not modify the workspace; each query provides a consistent view of the graph.
- Queries signal failure without side effects when the graph source fails (the graph is unmodified).
- Node labels are valid Bazel target labels (a precondition); unknown labels are unexpected and not covered by this contract.

**Assumptions**

- The workspace graph is accessible.
- Node targets declare all dependencies they consume.
- Node IDs are valid Bazel target labels.
- The graph topology is acyclic.

## Non-concerns

- Graph-source mechanism: how the graph is read from the configured source is unspecified.
- Build execution: the component never executes builds; it provides the graph and storage as data.
