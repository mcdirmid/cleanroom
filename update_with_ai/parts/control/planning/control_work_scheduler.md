<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: cf282bfc364a
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# control_work_scheduler interface component

imports: agent_session, dag_storage, dag_subgraph, agent_node_config

## Intent

The control_work_scheduler interface component defines contracts for discovering ready dirty nodes across subgraphs or directory scopes, ranking roles dynamically without hardcoded ordering, and synthesizing task prompts with feedback.

Multi-stage Cleanroom pipelines require progressive execution where upstream artifacts are produced before downstream consumers run. By computing role depth dynamically from declared role dependencies, new roles and custom pipelines are supported automatically without modifying scheduling logic.

## Factored Contracts

### Typing

- A scheduled task encapsulates a target node, synthesized prompt, upstream dependency paths, and defect feedback messages.
- A work schedule contains a sequence of scheduled tasks ready for execution.
- A work scheduler operates within the agent session lifecycle tier.

### Contracts

- A work scheduler discovers dirty candidate nodes within a specified execution subgraph. [discover_subgraph_candidates]
- A work scheduler discovers dirty candidate nodes matching a specified directory path. [discover_directory_candidates]
- A work scheduler filters candidate nodes whose direct non-silent dependencies in graph storage are clean. [filter_ready_dependencies]
- A work scheduler computes role precedence rank dynamically from declared role dependency topological depth. [compute_role_precedence]
- A work scheduler sorts ready nodes by dynamic role precedence rank. [sort_nodes_by_precedence]
- A work scheduler truncates ready nodes to a requested batch size limit. [limit_scheduled_batch]
- A work scheduler formats the role prompt template with unit and component names. [format_task_prompt]
- A work scheduler retrieves unresolved defect feedback messages from graph storage for each task. [retrieve_task_feedback]

### Woven Contracts

- When discovering work in an execution subgraph, the scheduler identifies ready dirty candidates, sorts them by dynamic role depth, limits the batch, and synthesizes task prompts. [discover_subgraph_candidates, filter_ready_dependencies, compute_role_precedence, sort_nodes_by_precedence, limit_scheduled_batch, format_task_prompt, retrieve_task_feedback]
- When discovering work in a directory scope, the scheduler identifies matching dirty nodes, filters for clean upstream dependencies, orders them by role depth, and builds scheduled tasks. [discover_directory_candidates, filter_ready_dependencies, compute_role_precedence, sort_nodes_by_precedence, limit_scheduled_batch, format_task_prompt, retrieve_task_feedback]

## Grounding

### Knowledge Provisions

- Computes ready dirty nodes sorted by topological role depth into scheduled work batches. [work_schedule_provision]
- Computes role precedence rank dynamically from declared role dependencies. [role_precedence_provision]

### Knowledge Requirements

- Inspection of dirty node status and upstream dependency cleanliness in graph storage.
  - Deferred: Queried from DagStorage in implementation.
- Topological analysis of declared role dependencies to derive role execution depth.
  - Deferred: Derived from role configuration in implementation.
- Resolution of prompt templates and formatting of task prompts with feedback history.
  - Deferred: Formatted using role prompt templates in implementation.
