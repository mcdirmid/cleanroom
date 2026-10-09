<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: f145a180c39d
-->

# loop_node_cleaner interface component

imports: dag_storage

## Purpose

The loop_node_cleaner interface component provides an abstraction for executing single-node task workloads, updating node state in dag storage, and signaling workflow continuation.

Multi-step build and agent workflows execute heterogeneous tasks—such as code generation, verification, and file editing—across individual graph nodes. Hardcoding specific task runners or message delivery mechanics into graph orchestrators creates monolithic coupling and prevents varying execution environments. The loop_node_cleaner interface component establishes an extensible execution boundary where a node cleaner directly manages its node state and message delivery in dag storage, communicating only whether graph processing can continue.

**Out of scope:** The loop_node_cleaner interface component does not schedule topological graph traversal or evaluate global graph completion; these are handled by other components.

## Types and Behavior

A polymorphic *node cleaner* cleans nodes sharing a role.

A node cleaner can *clean* dirty nodes, communicating whether processing should *continue*. Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node; otherwise, processing continues.
