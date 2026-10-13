<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:16Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Name the node cleaning capability canonically and state the continuation invariant declaratively
CODE_HASH: 8207d6f64baf
SPEC_QA_AUDIT: 2026-10-13T20:42:16Z
-->

# loop_node_cleaner interface component

imports: dag_storage

## Purpose

The loop_node_cleaner interface component provides an abstraction for executing single-node task workloads, updating node state in dag storage, and signaling workflow continuation.

Multi-step build and agent workflows execute heterogeneous tasks, such as code generation, verification, and file editing, across individual graph nodes. Hardcoding specific task runners or message delivery mechanics into graph orchestrators creates monolithic coupling and prevents varying execution environments. The loop_node_cleaner interface component establishes an extensible execution boundary where a node cleaner directly manages its node state and message delivery in dag storage, communicating only whether graph processing can continue.

**Out of scope:** The loop_node_cleaner interface component does not schedule topological graph traversal or evaluate global graph completion; these are handled by other components.

## Types and Behavior

A polymorphic *node cleaner* cleans the dirty nodes that share a role.

A node cleaner can *clean nodes*, communicating whether processing should *continue*. Processing cannot continue only when cleaning fails for nodes that no other node cleaning can address; otherwise processing continues.
