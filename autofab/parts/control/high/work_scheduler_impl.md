# work_scheduler_impl implementation component

imports: session, dag_storage, subgraph, node_config, agent_config
implements: work_scheduler

## Purpose

The work_scheduler_impl implementation component realizes ready-node discovery across subgraph and directory scopes, topological role ranking, and prompt formatting.

Autonomous execution requires precise dependency evaluation so that tasks whose upstream dependencies are incomplete or failed are never presented as ready work. The work_scheduler_impl implementation component traverses the execution graph to identify dirty nodes with satisfied upstream dependencies, resolves role precedence dynamically by computing the longest dependency path in the role definition graph, and builds structured task prompts detailing target files, role expectations, and historical feedback.

**Out of scope:** The work_scheduler_impl implementation component does not persist node status changes or execute verification commands; these are handled by other components.

**Delegated:** Graph traversal and dependency queries are delegated to subgraph.

## Types and Behavior

The work scheduler implements work scheduling for an agent session.

When discovering ready tasks:

- The work scheduler queries the subgraph for ready dirty candidates using the dynamic role order when an execution subgraph is provided.

- The work scheduler scans nodes in storage matching the directory path when a directory scope is provided without a subgraph, filtering for nodes whose status is dirty and whose direct non-silent upstream dependencies in graph storage are clean.

- The work scheduler computes role precedence dynamically by inspecting the declared role dependencies of the role configuration and assigning each role a precedence rank equal to its maximum topological depth from root roles, guaranteeing that upstream phases take precedence over downstream phases regardless of role naming.

- The work scheduler formats a task prompt for each ready node within the requested batch limit, using the configured role prompt template, substituting target unit paths and component names, and collecting the open feedback messages from graph storage into a feedback review section.

- The work scheduler formats dependency paths for scheduled tasks using user-facing file aliases rather than raw graph addresses.

- When formatting task prompts for auditor sessions, the work scheduler lists configured blame targets against grounding specifications, states that all workspace files are read-only, directs running check_files to verify each target, submitting when checks pass, and blaming culprit files with critiques when checks fail.

- When formatting task prompts for multi-node sessions, the work scheduler instructs the agent to specify target parameters using file paths.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
