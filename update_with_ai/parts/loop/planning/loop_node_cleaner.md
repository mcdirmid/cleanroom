<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 8198b5344edc
-->

# loop_node_cleaner interface component

imports: dag_storage

## Intent

Multi-step build and agent workflows execute heterogeneous tasks—such as code generation, verification, and file editing—across individual graph nodes. Hardcoding specific task runners or message delivery mechanics into graph orchestrators creates monolithic coupling and prevents varying execution environments. The loop_node_cleaner interface component establishes an extensible execution boundary where a node cleaner directly manages its node state and message delivery in dag storage, communicating only whether graph processing can continue.

By isolating role execution and failure reporting into a polymorphic cleaner interface, orchestrators can schedule batch workloads without concern for concrete agent session lifecycles.

## Factored Contracts

### Contracts

- A caller supplies dirty nodes when cleaning nodes. [clean_nodes_supplied]
- A node cleaner cleans dirty nodes sharing a role. [clean_dirty_nodes]
- The node cleaner communicates whether processing should continue. [communicate_processing_continuation]
- Processing cannot continue only if an unhandleable failure occurs while cleaning the nodes. [cannot_continue_on_unhandleable_failure]
- Processing continues when cleaning completes without unhandleable failure. [continue_when_cleaning_handled]

### Woven Contracts

- A node cleaner processes supplied dirty nodes sharing a role and returns whether workflow processing can continue. [clean_nodes_supplied, clean_dirty_nodes, communicate_processing_continuation, cannot_continue_on_unhandleable_failure, continue_when_cleaning_handled, dag_storage: [expose_node_dirty]]

## Grounding

### Knowledge Provisions

- Node cleaning execution for batches of dirty nodes sharing a role. [node_cleaner_service]

### Knowledge Requirements

- Execution environment orchestration for agent session phases.
  - Deferred: Managed via agent session lifecycle and loop driver in implementation.
- Translation of execution outcomes into graph storage mutations.
  - Deferred: Commits clean state, change messages, or blame feedback in implementation.
