# dag_node_cleaner

imports: dag_storage
types from dag_storage: node, pending message

## Purpose

Executes single-node task logic, consuming pending messages and producing change or feedback outcomes.

A dirty task node must consume incoming invalidations and execute its isolated workload to produce updated artifacts. The node cleaner processes a node's pending messages, producing change messages when new outputs are created or feedback messages when upstream inputs require correction.

## Types

- A *node cleaner* is a service that cleans an individual *node* using its *pending messages*
- A *change message* is a message produced by cleaning a *node*, communicating modifications to downstream dependents
- A *feedback message* is a message produced by cleaning a *node*, communicating issues to upstream dependencies

## Behavior

- A *node cleaner* cleans a dirty *node* by processing its *pending messages*.
- Cleaning a *node* produces *change messages* to notify reverse dependencies of updated artifacts.
- Cleaning a *node* produces *feedback messages* to notify dependencies of defects or required revisions.
