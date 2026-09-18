# dag_asm assembly component

assembles: dag_subgraph_impl
imports: dag_config, dag_storage
implements: dag_subgraph

## Purpose

The dag_asm assembly component aggregates topological subgraph queries and bounded visit tracking into the directed acyclic graph subsystem assembly.

Coordinating multi-node task resolution requires traversing dependency relationships in topological order, isolating active execution subgraphs, and evaluating dirty node readiness without permitting runaway re-cleaning loops. Without a focused assembly boundary, graph traversal mechanics risk tight coupling to concrete node executors and message serialization formats. The dag_asm assembly component aggregates the topological subgraph query implementation into a dedicated subsystem, closing the dag subgraph interface while declaring dependencies on graph storage and configuration.

**Out of scope:** The dag_asm assembly component does not execute agent turn loops, format file aliases, or parse build manifests; these are handled by other components.

## Types and Behavior

The *dag assembly* unites the concrete implementation components that realize dependency-first topological graph queries and execution iteration bounds. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The dag assembly aggregates the dag subgraph implementation from dag_subgraph_impl, closing the dag subgraph interface to query active subgraphs in dependency-first order, batch ready dirty nodes, and enforce execution iteration limits.
