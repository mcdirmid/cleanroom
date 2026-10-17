<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T19:43:56Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Reduce assembly narrative to a single structural sentence and remove constituent naming from prose
CODE_HASH: abfd4d938099
SPEC_QA_AUDIT: 2026-10-15T19:43:56Z
-->

# dag_asm assembly component

assembles: subgraph_impl
imports: dag_config, dag_storage
implements: subgraph

## Purpose

The dag_asm assembly component aggregates topological subgraph queries and bounded visit tracking into the directed acyclic graph subsystem assembly.

Coordinating multi-node task resolution requires traversing dependency relationships in topological order, isolating active execution subgraphs, and evaluating dirty node readiness without permitting runaway re-cleaning loops. Without a focused assembly boundary, graph traversal mechanics risk tight coupling to concrete node executors and message serialization formats. The dag_asm assembly component aggregates the topological subgraph query implementation into a dedicated subsystem, closing the dag subgraph interface while declaring dependencies on graph storage and configuration.

**Out of scope:** The dag_asm assembly component does not execute agent turn loops, format file aliases, or parse build manifests; these are handled by other components.

## Types and Behavior

The dag_asm assembly component aggregates the implementation of the dag subgraph interface, providing a unified assembly for dependency-first topological graph queries and execution iteration bounds.
