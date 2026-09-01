# node_id_utils

imports: dag_storage
types from dag_storage: node

## Purpose

Provides operations for normalizing node identifier strings and resolving package directories from opaque nodes.

Multi-step workflows require deterministic node addressing and durable state storage within project package structures. Node identifier utilities define abstract capabilities to convert arbitrary string identifiers into canonical node references and resolve the filesystem package directories holding them, shielding graph storage and runner logic from build-system-specific label syntax.

## Types

- A *node directory* is a filesystem path addressing the workspace package directory of a *node*
- A *node identifier utility* is a service that normalizes node identifiers and resolves *node directories*

## Behavior

- A *node identifier utility* normalizes an arbitrary target identifier string into a canonical *node*.
- A *node identifier utility* extracts a *node directory* from a *node*.
