<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 0170083672a7
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# agent_storage interface component

imports: dag_storage

## Intent

Task execution across structured projects requires maintaining target dependency relationships alongside durable node state. The agent_storage interface component preserves propagating and non-propagating graph relationships, task prompts, and node definitions populated from workspace target manifests, while evaluating node dirty state and pending messages backed by in-band source file metadata.

By extending dag storage with manifest-backed node definitions and prompt metadata, the component provides a unified graph authority for scheduling node cleaning passes.

## Factored Contracts

### Typing

- A task prompt is an instruction describing the work required to clean a node.
- A node definition encapsulates a declared target's execution configuration, role attributes, and task prompts.

### Contracts

- A caller supplies a dag node when querying node definitions. [query_node_def_supplied]
- A caller supplies a dag node when querying task prompts. [query_task_prompt_supplied]
- The agent storage is a system service that is a dag storage backed by workspace build target manifests. [agent_storage_is_dag_storage]
- The agent storage maintains nodes and dependencies from workspace targets. [maintain_workspace_targets]
- The agent storage provides task prompts for declared nodes. [provide_task_prompts]
- The agent storage provides node definitions for declared nodes. [provide_node_definitions]
- The agent storage evaluates node dirty status and derives pending messages from in-band source file metadata. [evaluate_dirty_from_source_metadata]

### Woven Contracts

- When querying a declared node, the agent storage provides its task prompt and node definition. [query_node_def_supplied, query_task_prompt_supplied, provide_task_prompts, provide_node_definitions]
- When a propagating dependency changes, dependent nodes dynamically evaluate as dirty based on dependency change timestamps. [evaluate_dirty_from_source_metadata, dag_storage: [expose_node_dirty, dirty_when_dependency_newer]]

## Grounding

### Knowledge Provisions

- Manifest-backed graph storage with task prompts and node definitions. [agent_storage_service]

### Knowledge Requirements

- Target manifest discovery and in-band source file metadata parsing.
  - Deferred: Provided by storage implementation using manifest readers and src_metadata_ext.
