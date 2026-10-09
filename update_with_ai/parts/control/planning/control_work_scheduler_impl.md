<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 867cdaecca31
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# control_work_scheduler_impl implementation component

imports: agent_session, dag_storage, dag_subgraph, agent_node_config, agent_config
implements: control_work_scheduler

## Intent

The control_work_scheduler_impl implementation component realizes DAG query evaluation, topological role depth sorting, directory pattern matching, and task prompt string templating.

Computing role depth dynamically replaces fragile static dictionaries. The implementation traverses role definitions to compute longest dependency chains, queries graph storage for node cleanliness, resolves prompt templates using string formatting, and aggregates historical feedback into structured prompt blocks.

## Factored Contracts

### Contracts

- The work scheduler queries role definitions to determine declared role dependencies. [query_role_definitions]
- The work scheduler builds a directed acyclic graph of role dependencies. [build_role_dag]
- The work scheduler calculates the longest path from root roles to determine each role's depth. [calculate_role_depth]
- The work scheduler scans storage nodes whose unit address falls within the specified directory. [scan_directory_nodes]
- The work scheduler queries graph storage node status for dirty state. [query_node_status]
- The work scheduler queries graph storage dependency edges to verify upstream cleanliness. [check_upstream_cleanliness]
- The work scheduler formats prompt variables for unit directory, unit name, and component type. [substitute_prompt_variables]
- The work scheduler appends feedback messages into a formatted feedback review section. [append_feedback_section]

### Woven Contracts

- When sorting candidate tasks, the scheduler builds the role dependency graph, calculates role depth, and orders nodes by ascending depth. [query_role_definitions, build_role_dag, calculate_role_depth, control_work_scheduler: [sort_nodes_by_precedence]]
- When scheduling by directory, the scheduler scans directory nodes, verifies dirty status, checks that non-silent dependencies are clean, and formats task prompts. [scan_directory_nodes, query_node_status, check_upstream_cleanliness, substitute_prompt_variables, append_feedback_section, control_work_scheduler: [limit_scheduled_batch]]

## Grounding

### Knowledge Provisions

- Computes ready dirty nodes sorted by topological role depth into scheduled work batches. [work_schedule_provision]
- Computes role precedence rank dynamically from declared role dependencies. [role_precedence_provision]

### Inherited Deferred Requirements

- Inspection of dirty node status and upstream dependency cleanliness in graph storage.
  - Grounded: [dag_storage: [dag_storage_service]]
- Topological analysis of declared role dependencies to derive role execution depth.
  - Grounded: [agent_config: [agent_configuration_parameters], agent_node_config: [node_configuration_service], role_precedence_provision]
- Resolution of prompt templates and formatting of task prompts with feedback history.
  - Grounded: [agent_node_config: [node_configuration_service], dag_storage: [dag_storage_service]]

### Knowledge Requirements

- Filtering and scanning candidate nodes within subgraphs or directory path patterns.
  - Grounded: [dag_subgraph: [dag_subgraph_service], dag_storage: [dag_storage_service]]
