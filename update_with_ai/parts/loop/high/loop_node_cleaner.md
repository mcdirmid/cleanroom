# loop_node_cleaner interface component

imports: dag_storage

## Purpose

The loop_node_cleaner interface component provides an abstraction for executing single-node task workloads, updating node state in dag storage, and signaling workflow continuation.

Multi-step build and agent workflows execute heterogeneous tasks—such as code generation, verification, and file editing—across individual graph nodes. Hardcoding specific task runners or message delivery mechanics into graph orchestrators creates monolithic coupling and prevents varying execution environments. The loop_node_cleaner interface component establishes an extensible execution boundary where a node cleaner directly manages its node state and message delivery in dag storage, communicating only whether graph processing can continue.

**Out of scope:** The loop_node_cleaner interface component does not schedule topological graph traversal or evaluate global graph completion; these are handled by other components.

## Types and Behavior

A *node cleaner* is a polymorphic service that cleans nodes sharing a role.

A node cleaner can *clean* dirty nodes, communicating whether processing should *continue*. Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node; otherwise, processing continues.

