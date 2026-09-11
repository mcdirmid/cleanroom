# dag_asm assembly component

assembles: dag_cleaner_impl
imports: dag_node_cleaner, dag_storage
implements: dag_cleaner

## Purpose

The dag_asm assembly component aggregates topological graph traversal and bounded dependency cleaning into the directed acyclic graph subsystem assembly.

Coordinating multi-node task resolution requires traversing dependency relationships in topological order and re-evaluating node dirty status without permitting runaway re-cleaning loops. Without a focused assembly boundary, graph traversal mechanics risk tight coupling to concrete node executors and message serialization formats. The dag_asm assembly component aggregates the topological cleaner implementation into a dedicated subsystem, closing the dag cleaner interface while declaring dependencies on abstract node cleaners and graph storage.

**Out of scope:** The dag_asm assembly component does not execute agent turn loops, format file aliases, or parse build manifests; these are handled by other components.

## Types and Behavior

The *dag assembly* unites the concrete implementation components that realize dependency-first topological graph cleaning and execution iteration bounds. The assembly initializes its constituent implementation components and registers their singleton services with the system lifecycle prototype.

The dag assembly aggregates the following implementation components:

- The dag cleaner implementation from dag_cleaner_impl, closing the dag cleaner interface to visit reachable graph nodes in dependency-first order and enforce execution iteration limits.
