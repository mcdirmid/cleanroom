# work_scheduler_impl implementation component

## Intent

The work_scheduler_impl implementation component realizes DAG query evaluation, topological role depth sorting, directory pattern matching, and task prompt string templating.

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
- The work scheduler formats scheduled task dependency paths as user-facing file aliases rather than raw graph addresses. [format_file_alias_dependency_paths]
- The work scheduler formats auditor task prompts with blame targets against grounding files and read-only directives. [format_auditor_session_instructions]
- The work scheduler formats multi-node task prompts with instructions to specify targets as file paths. [format_multi_node_file_path_instructions]

### Woven Contracts

- When sorting candidate tasks, the scheduler builds the role dependency graph, calculates role depth, and orders nodes by ascending depth. [query_role_definitions, build_role_dag, calculate_role_depth, work_scheduler: [sort_nodes_by_precedence]]
- When scheduling by directory, the scheduler scans directory nodes, verifies dirty status, checks that non-silent dependencies are clean, and formats task prompts. [scan_directory_nodes, query_node_status, check_upstream_cleanliness, substitute_prompt_variables, append_feedback_section, work_scheduler: [limit_scheduled_batch]]
- When formatting scheduled tasks and prompts, the scheduler converts dependency paths to file aliases, provides auditor directives for auditor roles, and directs file path targets for multi-node sessions. [format_file_alias_dependency_paths, format_auditor_session_instructions, format_multi_node_file_path_instructions, work_scheduler: [format_task_prompt]]

## Grounding

### Knowledge Provisions

- Computes ready dirty nodes sorted by topological role depth into scheduled work batches. [work_schedule_provision]
- Computes role precedence rank dynamically from declared role dependencies. [role_precedence_provision]

### Inherited Deferred Requirements

- Inspection of dirty node status and upstream dependency cleanliness in graph storage.
  - Grounded: [dag_storage: [dag_storage_service]]
- Topological analysis of declared role dependencies to derive role execution depth.
  - Grounded: [agent_config: [agent_configuration_parameters], node_config: [node_configuration_service], role_precedence_provision]
- Resolution of prompt templates and formatting of task prompts with feedback history.
  - Grounded: [node_config: [node_configuration_service], dag_storage: [dag_storage_service]]

### Knowledge Requirements

- Filtering and scanning candidate nodes within subgraphs or directory path patterns.
  - Grounded: [subgraph: [dag_subgraph_service], dag_storage: [dag_storage_service]]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
