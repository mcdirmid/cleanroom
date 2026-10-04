# agent_storage interface component

imports: dag_storage

## Intent

Task execution across structured projects requires maintaining target dependency relationships alongside durable inter-node messages. The agent_storage interface component preserves propagating and non-propagating graph relationships, task prompts, and node definitions populated from workspace target manifests, while maintaining pending messages and reverse dependencies for nodes.

By extending dag storage with manifest-backed node definitions and prompt metadata, the component provides a unified graph authority for scheduling node cleaning passes.

## Factored Contracts

### Typing

- A task prompt is an instruction describing the work required to clean a node.
- A node definition is metadata describing task prompts for a node.

### Contracts

- A caller supplies a dag node when querying node definitions. [query_node_def_supplied]
- A caller supplies a dag node when querying task prompts. [query_task_prompt_supplied]
- The agent storage is a system service that is a dag storage backed by workspace build target manifests. [agent_storage_is_dag_storage]
- The agent storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets. [maintain_workspace_targets]
- The agent storage provides task prompts for declared nodes. [provide_task_prompts]
- The agent storage provides node definitions for declared nodes. [provide_node_definitions]
- The agent storage marks dependent nodes dirty when propagating dependencies change. [mark_dependents_dirty_on_change]

## Woven Contracts

- When querying a declared node, the agent storage provides its task prompt and node definition. [query_node_def_supplied, query_task_prompt_supplied, provide_task_prompts, provide_node_definitions]
- When a propagating dependency changes, registered dependent nodes in agent storage are marked dirty. [mark_dependents_dirty_on_change, dag_storage: [register_node_dependent, expose_node_dirty, dirty_when_messages_present]]
