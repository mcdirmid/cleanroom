# build_message_store

imports: dag_storage (node, message, message kind, pending message, reverse dependency), build_graph_storage (package directory)
terms (from dag_storage): node, message, message kind, pending message, reverse dependency
terms (from build_graph_storage): package directory
terms (owned): package message data, textproto format

## Purpose

Provides persistence and retrieval of node messages and known reverse dependencies stored in per-package protobuf text-format files.

## Terms

- Package message data: the stored messages and known reverse dependencies belonging to targets in a specific package directory.
- Textproto format: the serialized protobuf text format encoding package message data according to the update_with_ai schema.

## Contract

**Inputs**

- A package directory path and node ID.
- For mutation: messages or reverse dependency labels.

**Operations**

- Read pending messages for a node from its package directory.
- Add or set pending messages for a node.
- Clear a node's pending messages or delete a node's entry.
- Read, add, or clear known reverse dependencies for a node.

**Guarantees**

- All nodes defined in the same package share that package's message file (.update_with_ai.textproto).
- Message kinds are persisted alongside message text.
- Operations on missing package files treat them as empty and create them on write.
- Atomic file updates preserve previously stored messages on failure.

**Assumptions**

- Package directories are valid filesystem paths.

## Non-concerns

- Concurrency locking across processes: unspecified.
