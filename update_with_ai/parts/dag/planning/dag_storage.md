<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-08T00:31:17Z
CHANGE: Update dag_storage factored contracts: mark_node_dirty, mark_subgraph_clean, add_feedback_message, and refined change message semantics
CODE_HASH: 96322a7cfc2a
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

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
- A change message is a dag message informing how an upstream dependency changed.
- A feedback message is a dag message blaming a specific dependency target node for defects detected by downstream dependents.

### Contracts

- A caller supplies a dag node when querying dependencies. [query_dependencies_node_supplied]
- A caller supplies a dag node when querying messages. [query_messages_node_supplied]
- A caller supplies a dag node when querying dirty status. [query_dirty_node_supplied]
- A caller supplies a dag node when adding a feedback message. [add_feedback_node_supplied]
- A caller supplies a feedback message when adding a feedback message. [add_feedback_msg_supplied]
- A caller supplies a dag node when marking a node dirty. [mark_dirty_node_supplied]
- A caller supplies a dag node when marking a subgraph clean. [mark_subgraph_clean_node_supplied]
- A caller supplies a dag node when marking a node clean. [mark_clean_node_supplied]
- Direct upstream dependencies of a dag node form a directed acyclic graph. [dependencies_form_dag]
- A system's dag storage provides access to a node's dag dependencies. [access_dag_dependencies]
- A system's dag storage provides access to messages for a node. [access_node_messages]
- A system's dag storage adds feedback messages blaming dependency target nodes. [add_feedback_messages]
- Adding a feedback message blaming a dependency target node records unacted feedback in its in-band metadata. [record_feedback_in_metadata]
- A system's dag storage marks a node dirty. [mark_node_dirty]
- Marking a node dirty removes its clean status in in-band metadata. [mark_dirty_clears_clean_status]
- A system's dag storage marks a subgraph clean. [mark_subgraph_clean]
- Marking a subgraph clean marks the target node clean. [subgraph_clean_marks_target_clean]
- Marking a subgraph clean marks all reachable dependencies clean. [subgraph_clean_marks_dependencies_clean]
- A system's dag storage exposes whether a node is dirty. [expose_node_dirty]
- A node is considered dirty when its source artifact is missing on disk. [dirty_when_source_missing]
- A node is considered dirty when its in-band metadata is missing. [dirty_when_metadata_missing]
- A node is considered dirty when its in-band metadata is invalid. [dirty_when_metadata_invalid]
- A node is considered dirty when its in-band metadata is uncleaned with a change description. [dirty_when_metadata_uncleaned]
- A node is considered dirty when marked dirty with a dirty tag. [dirty_when_metadata_dirty]
- A node is considered dirty when unacted feedback messages exist. [dirty_when_feedback_present]
- Any non-silent dependency was changed after the node was last cleaned marks a node dirty. [dirty_when_dependency_newer]
- A system's dag storage materializes initial templates on disk for a node when its source artifact is missing. [materialize_node_template]
- A system's dag storage marks a node clean in graph storage, clearing messages and stamping clean metadata. [mark_node_clean_in_storage]
- Marking a node clean with a change message updates its change timestamp in in-band metadata. [mark_clean_updates_change_timestamp]
- Marking a node clean with a change message records the change message content in in-band metadata. [mark_clean_records_change_summary]
- Marking a node clean clears unacted feedback entries. [mark_clean_clears_feedback]
- Marking a node clean clears dirty tags. [mark_clean_clears_dirty_tags]
- When marking an auditor node clean, audit metadata is stamped on feedback dependencies. [mark_auditor_node_clean_stamps_dependencies]

### Woven Contracts

- When querying whether a node is dirty, dirty status is true if the source file is missing, if metadata is missing, invalid, or uncleaned, if a dirty tag is present, if feedback is present, or if a non-silent dependency changed after the node was last cleaned. [query_dirty_node_supplied, expose_node_dirty, dirty_when_source_missing, dirty_when_metadata_missing, dirty_when_metadata_invalid, dirty_when_metadata_uncleaned, dirty_when_metadata_dirty, dirty_when_feedback_present, dirty_when_dependency_newer]
- When adding a feedback message, the feedback explanation is recorded into in-band metadata for the blamed dependency target node. [add_feedback_node_supplied, add_feedback_msg_supplied, add_feedback_messages, record_feedback_in_metadata]
- When marking a node dirty, its clean status is cleared in in-band metadata. [mark_dirty_node_supplied, mark_node_dirty, mark_dirty_clears_clean_status]
- When marking a subgraph clean, missing templates are materialized and all reachable nodes in the subgraph are marked clean. [mark_subgraph_clean_node_supplied, mark_subgraph_clean, subgraph_clean_marks_target_clean, subgraph_clean_marks_dependencies_clean, materialize_node_template, mark_node_clean_in_storage]
- When marking a node clean with a change message, change metadata is updated and unacted feedback and dirty status are cleared. [mark_clean_node_supplied, mark_node_clean_in_storage, mark_clean_updates_change_timestamp, mark_clean_records_change_summary, mark_clean_clears_feedback, mark_clean_clears_dirty_tags]
- When accessing messages for a node, diagnostic change and feedback explanations are returned. [query_messages_node_supplied, access_node_messages]

## Grounding

### Knowledge Provisions

- In-band dirty status evaluation, dependency queries, and diagnostic message recording. [dag_storage_service]

### Knowledge Requirements

- Source artifact inspection and in-band header parsing on the underlying filesystem.
  - Deferred: Provided by storage implementation using filesystem and metadata components.
- Stamping clean metadata, clearing messages, and template materialization on disk.
  - Deferred: Provided by storage implementation modifying source artifacts on disk.
