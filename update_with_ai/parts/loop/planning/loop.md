# loop interface component

imports: dag_storage

## Intent

Executing multi-stage agent workflows across interdependent graph structures requires evaluating dirty state and coordinating cleaning passes in dependency order. Without a centralized orchestration boundary, callers must manually coordinate node invalidations, state transitions, and change notifications across graph storage. The loop interface component coordinates this end-to-end lifecycle: dispatching cleaning passes across target subgraphs, routing feedback into target nodes, and broadcasting change messages to reverse dependencies.

By managing end-to-end cleaning runs, injecting change and feedback messages, and propagating notifications to dependents, the loop isolates build coordination complexity from execution runners.

## Factored Contracts

### Typing

- A cleaning pass is an execution run that cleans dirty nodes across a target subgraph.
- A build result indicates overall success.
- A build result provides an execution summary.

### Contracts

- A caller supplies a target node in graph storage when executing a cleaning pass. [clean_pass_target_supplied]
- The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage. [execute_cleaning_pass]
- The loop produces a build result upon pass completion. [produce_build_result]
- A caller supplies a target node when marking a target node dirty. [mark_dirty_target_supplied]
- A caller supplies a change message when marking a target node dirty. [mark_dirty_message_supplied]
- The loop marks a target node dirty by injecting a change message into its pending messages. [mark_node_dirty]
- A caller supplies a target node when injecting a feedback message. [inject_feedback_target_supplied]
- A caller supplies a feedback message when injecting a feedback message. [inject_feedback_message_supplied]
- The loop injects a caller-supplied feedback message into a target node. [inject_feedback_message]
- A caller supplies a node when broadcasting a change message. [broadcast_change_node_supplied]
- A caller supplies a change message when broadcasting a change message. [broadcast_change_message_supplied]
- The loop broadcasts a caller-supplied change message from a node to all of its reverse dependencies. [broadcast_change_message]

## Woven Contracts

- Executing a cleaning pass traverses the subgraph rooted at a target node and yields a build result. [clean_pass_target_supplied, execute_cleaning_pass, produce_build_result, dag_storage: [access_dag_dependencies]]
- Injecting change or feedback messages records diagnostic updates in target node messages. [mark_dirty_target_supplied, mark_dirty_message_supplied, mark_node_dirty, inject_feedback_target_supplied, inject_feedback_message_supplied, inject_feedback_message, dag_storage: [add_node_messages]]
- Broadcasting change messages propagates updates from a modified node across all registered reverse dependencies. [broadcast_change_node_supplied, broadcast_change_message_supplied, broadcast_change_message, dag_storage: [access_node_dependents, add_node_messages]]
