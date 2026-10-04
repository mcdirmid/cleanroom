# dag_storage interface component

## Intent

Multi-step agent workflows require coordinated incremental execution to avoid redundant re-computation and prevent stale task outputs. As tasks evolve, dependent stages must understand why upstream changes necessitate re-execution, and downstream stages must communicate diagnostic issues back to their prerequisites. The dag_storage interface component provides a dedicated graph coordination boundary that isolates lifecycle tracking and inter-node communication state from the operational mechanics of individual task execution.

By managing direct dependencies, silent exclusion rules, registered dependents, and diagnostic change and feedback messages, dag storage exposes dirty status indicating when a node requires cleaning.

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
- A caller supplies a dag node when querying dependents. [query_dependents_node_supplied]
- A caller supplies a dag node when querying messages. [query_messages_node_supplied]
- A caller supplies a dag node when querying dirty status. [query_dirty_node_supplied]
- A caller supplies a dag node when registering dependents. [register_dependent_node_supplied]
- A caller supplies a dag node when clearing dependents. [clear_dependents_node_supplied]
- A caller supplies a dag node when adding a message. [add_message_node_supplied]
- A caller supplies a dag message when adding a message. [add_message_msg_supplied]
- A caller supplies a dag node when clearing messages. [clear_messages_node_supplied]
- Direct upstream dependencies of a dag node form a directed acyclic graph. [dependencies_form_dag]
- A system's dag storage provides access to a node's dag dependencies. [access_dag_dependencies]
- A system's dag storage registers a node as a dependent to all of its non-silent dependencies. [register_node_dependent]
- A system's dag storage provides access to dependents registered to a node. [access_node_dependents]
- A system's dag storage clears dependents registered to a node. [clear_node_dependents]
- A system's dag storage adds messages to a node. [add_node_messages]
- A system's dag storage accesses messages for a node. [access_node_messages]
- A system's dag storage clears messages from a node. [clear_node_messages]
- A system's dag storage exposes whether a node is dirty. [expose_node_dirty]
- Silent dependencies are excluded when registering a node as a dependent. [exclude_silent_dependencies]
- A node is considered dirty when the node has messages. [dirty_when_messages_present]

## Woven Contracts

- When registering a node across its dependencies, only non-silent dependencies register the node as a dependent. [register_dependent_node_supplied, register_node_dependent, exclude_silent_dependencies]
- When querying whether a node is dirty, dirty status is true if the node contains messages. [query_dirty_node_supplied, access_node_messages, expose_node_dirty, dirty_when_messages_present]
- When adding a message to a node, the message is stored for that node. [add_message_node_supplied, add_message_msg_supplied, add_node_messages]
- When clearing messages from a node, all stored messages for the node are removed. [clear_messages_node_supplied, clear_node_messages]
- When clearing dependents from a node, all registered dependents for the node are removed. [clear_dependents_node_supplied, clear_node_dependents]
