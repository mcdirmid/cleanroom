# dag_storage interface component

## Intent

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

By managing direct dependencies, silent exclusion rules, diagnostic change messages, and feedback records, dag storage exposes dirty status indicating when a node requires cleaning without persisting reverse dependencies to disk.

## Factored Contracts

### Typing

- A dag node has a unit address.
- A dag node has a role address.
- A dag dependency refers to a direct upstream node.
- A dag dependency indicates whether the dependency is silent.
- A dag message provides explanatory text content explaining why a node requires cleaning.
- A change message is a dag message informing of changes made to upstream dependencies.
- A feedback message is a dag message blaming a specific dependency target node for defects detected by downstream dependents.

### Contracts

- A caller supplies a dag node when querying dependencies. [query_dependencies_node_supplied]
- A caller supplies a dag node when querying messages. [query_messages_node_supplied]
- A caller supplies a dag node when querying dirty status. [query_dirty_node_supplied]
- A caller supplies a dag node when recording feedback messages. [record_feedback_node_supplied]
- A caller supplies a feedback message when recording feedback messages. [record_feedback_msg_supplied]
- A caller supplies a dag node when recording change messages. [record_change_node_supplied]
- A caller supplies a change message when recording change messages. [record_change_msg_supplied]
- Direct upstream dependencies of a dag node form a directed acyclic graph. [dependencies_form_dag]
- A system's dag storage provides access to a node's dag dependencies. [access_dag_dependencies]
- A system's dag storage provides access to messages for a node. [access_node_messages]
- A system's dag storage records feedback messages blaming dependency target nodes. [record_feedback_messages]
- A system's dag storage records change messages marking a target node dirty. [record_change_messages]
- Recording a change message against a target node marks it dirty by clearing its last cleaned status. [mark_dirty_on_change_message]
- A system's dag storage exposes whether a node is dirty. [expose_node_dirty]
- A node is considered dirty when its source artifact is missing on disk. [dirty_when_source_missing]
- A node is considered dirty when its in-band metadata is missing. [dirty_when_metadata_missing]
- A node is considered dirty when its in-band metadata is invalid. [dirty_when_metadata_invalid]
- A node is considered dirty when its in-band metadata is uncleaned with a change description. [dirty_when_metadata_uncleaned]
- A node is considered dirty when unacted feedback messages exist. [dirty_when_feedback_present]
- Any non-silent dependency was changed after the node was last cleaned marks a node dirty. [dirty_when_dependency_newer]
- A system's dag storage materializes initial templates on disk for a node when its source artifact is missing. [materialize_node_template]
- A system's dag storage marks a node clean in graph storage, clearing messages and stamping clean metadata. [mark_node_clean_in_storage]
- When a change description is provided, marking a node clean updates last changed timestamp and change description, and clears unacted feedback. [mark_clean_with_change_description]
- When marking an auditor node clean, audit metadata is stamped on feedback dependencies. [mark_auditor_node_clean_stamps_dependencies]

## Woven Contracts

- When querying whether a node is dirty, dirty status is true if the source file is missing, if metadata is missing, invalid, or uncleaned, if feedback is present, or if a non-silent dependency changed after the node was last cleaned. [query_dirty_node_supplied, expose_node_dirty, dirty_when_source_missing, dirty_when_metadata_missing, dirty_when_metadata_invalid, dirty_when_metadata_uncleaned, dirty_when_feedback_present, dirty_when_dependency_newer]
- When recording feedback messages, the feedback explanation is stored for the blamed dependency target node. [record_feedback_node_supplied, record_feedback_msg_supplied, record_feedback_messages]
- When recording change messages, the change description is recorded for the target node and its last cleaned status is cleared. [record_change_node_supplied, record_change_msg_supplied, record_change_messages, mark_dirty_on_change_message]
- When accessing messages for a node, diagnostic change and feedback explanations are returned. [query_messages_node_supplied, access_node_messages]
- When materializing a template for a node, boilerplate content is written to disk if the source file is missing without overwriting existing files. [materialize_node_template]
- When marking a node clean, messages are cleared and in-band metadata is updated so that the node is no longer dirty, stamping last changed and change description when supplied, or stamping audit metadata across feedback dependencies for auditor nodes. [mark_node_clean_in_storage, mark_clean_with_change_description, mark_auditor_node_clean_stamps_dependencies]
