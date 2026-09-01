# build_message_store

imports: dag_storage, node_id_utils
types from dag_storage: dag storage, node, message, pending message, reverse dependency
types from node_id_utils: node identifier utility, node directory

## Purpose

Persists node messages and recorded reverse dependencies in workspace package directories, enabling durable state across cleaning passes.

Inter-node build coordination requires storing unhandled messages and reverse dependencies durably in the workspace without losing state between runs. Build message store persists message queues and dependency relationships in per-package text files using node identifier utilities, providing atomic reads and writes.

## Types

- A *build message store* is a *dag storage* persistence layer storing node message data in package directories

## Behavior

- A *build message store* reads and writes *pending messages* and *reverse dependencies* for *nodes* in their package *node directories*.
- A *build message store* creates missing package message files on write and treats absent files as empty.
- Modifying messages or reverse dependencies in a *build message store* preserves existing records on failure.
