<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-05T20:52:01Z
LAST_CHANGED: 2026-10-04T23:01:55Z
CHANGE: new file
CODE_HASH: 35be00d70d66
-->

# loop interface component

imports: dag_storage

## Intent

Executing multi-stage agent workflows across interdependent graph structures requires evaluating dirty state and coordinating cleaning passes in dependency order. Without a centralized orchestration boundary, callers must manually coordinate node invalidations, state transitions, and change notifications across graph storage. The loop interface component coordinates this end-to-end lifecycle: dispatching cleaning passes across target subgraphs, routing feedback into target nodes, and recording change descriptions on modified nodes to dynamically invalidate downstream dependencies.

By managing end-to-end cleaning runs, injecting change and feedback messages, and recording change descriptions, the loop isolates build coordination complexity from execution runners.

## Factored Contracts

### Typing

- A cleaning pass is an execution run that cleans dirty nodes across a target subgraph.
- A build result indicates overall success.
- A build result provides an execution summary.

### Contracts

- A caller supplies a target node in graph storage when executing a cleaning pass. [clean_pass_target_supplied]
- The loop executes a cleaning pass over an acyclic subgraph rooted at a target node in graph storage. [execute_cleaning_pass]
- The loop produces a build result upon pass completion. [produce_build_result]
- A caller supplies a target node when marking an acyclic subgraph clean. [mark_clean_target_supplied]
- The loop marks all nodes in an acyclic subgraph clean, materializing missing source files from declared templates, initializing timestamps and default change descriptions, and clearing unacted feedback. [mark_subgraph_clean]
- A caller supplies a target node when marking a target node dirty. [mark_dirty_target_supplied]
- The loop marks a target node dirty by removing its last cleaned timestamp from in-band source metadata. [mark_node_dirty]
- A caller supplies a target node when injecting a feedback message. [inject_feedback_target_supplied]
- A caller supplies a feedback message when injecting a feedback message. [inject_feedback_message_supplied]
- The loop injects a caller-supplied feedback message into a target node. [inject_feedback_message]
- A caller supplies a target node when recording a change message. [record_change_node_supplied]
- A caller supplies a change message when recording a change message. [record_change_message_supplied]
- The loop records a caller-supplied change message on a target node in graph storage, updating in-band source metadata and dynamically invalidating downstream dependencies. [record_node_change_message]

## Woven Contracts

- Executing a cleaning pass traverses the subgraph rooted at a target node and yields a build result. \[clean_pass_target_supplied, execute_cleaning_pass, produce_build_result, dag_storage: [access_dag_dependencies]\]
- Marking an acyclic subgraph clean primes target and dependency source files with clean timestamps, materializing missing templates and clearing unacted feedback. \[mark_clean_target_supplied, mark_subgraph_clean, dag_storage: [access_dag_dependencies, clear_node_messages]\]
- Marking a target node dirty removes its last cleaned timestamp from in-band source metadata. \[mark_dirty_target_supplied, mark_node_dirty, dag_storage: [mark_node_dirty]\]
- Injecting feedback messages records diagnostic updates in target node messages. \[inject_feedback_target_supplied, inject_feedback_message_supplied, inject_feedback_message, dag_storage: [add_node_messages]\]
- Recording change messages updates a modified node in graph storage with a change description, clearing unacted feedback and dynamically invalidating downstream dependencies. \[record_change_node_supplied, record_change_message_supplied, record_node_change_message, dag_storage: [mark_clean_with_change_description]\]
