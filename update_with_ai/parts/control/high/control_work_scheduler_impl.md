# control_work_scheduler_impl implementation component

imports: agent_session, dag_storage, dag_subgraph, agent_node_config, agent_config
implements: control_work_scheduler

## Purpose

The control_work_scheduler_impl implementation component realizes ready-node discovery across subgraph and directory scopes, topological role ranking, and prompt formatting.

Autonomous execution requires precise dependency evaluation so that tasks whose upstream dependencies are incomplete or failed are never presented as ready work. The control_work_scheduler_impl implementation component traverses the execution graph to identify dirty nodes with satisfied upstream dependencies, resolves role precedence dynamically by computing the longest dependency path in the role definition graph, and builds structured task prompts detailing target files, role expectations, and historical feedback.

**Out of scope:** The control_work_scheduler_impl implementation component does not persist node status changes or execute verification commands; these are handled by other components.

**Delegated:** Graph traversal and dependency queries are delegated to dag_subgraph.

## Types and Behavior

The work scheduler implements work scheduling for the session.

When discovering ready tasks:

- When an execution subgraph is provided, the work scheduler queries the subgraph for ready dirty candidates using the dynamic role order.

- When a directory scope is provided without a subgraph, the work scheduler scans nodes in storage matching the directory path, filtering for nodes whose status is dirty and whose direct upstream non-silent dependencies in graph storage are clean.

- To compute role precedence dynamically, the work scheduler inspects declared role dependencies from role configuration, assigning each role a precedence rank equal to its maximum topological depth from root roles, guaranteeing that upstream phases always take precedence over downstream phases regardless of role naming.

- For each ready node within the requested batch limit, the work scheduler formats a task prompt using the configured role prompt template, substitutes target unit paths and component names, and collects open feedback messages from graph storage into a clear feedback review section.
