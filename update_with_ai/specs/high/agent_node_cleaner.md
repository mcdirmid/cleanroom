# agent_node_cleaner interface component

imports: dag_storage, dag_node_cleaner

## Purpose

The agent_node_cleaner interface component coordinates agent-driven node cleaning to resolve dirty workspace nodes within the dependency graph.

Autonomous graph execution requires cleaning dirty nodes through targeted agent problem solving without coupling graph coordination to execution harness specifics. Direct coupling of graph runners to prompt construction, execution harnesses, or tool environments prevents modular reuse and exposes graph algorithms to agent-level failure modes. The agent_node_cleaner interface component establishes an interface boundary between the dependency graph and agent-driven node execution, resolving dirty nodes within isolated agent sessions and translating outcomes into propagating graph messages.

**Out of scope:** The agent_node_cleaner interface component does not schedule topological graph walks, manage sandbox environments, or execute turn loops; these are handled by other components.

## Types and Behavior

The *agent node cleaner* is a system service that is a node cleaner.

An agent node cleaner cleans a dirty node within an agent session phase. Cleaning resolves the dirty node by:

- Producing change messages when workspace file modifications occur and task verification passes.

- Producing feedback messages containing the blame explanation and addressed to the blamed dependency node when blame is signaled.

- Leaving the node clean with no produced messages when cleaning succeeds without workspace file modifications.

- Leaving the node dirty with no produced messages and halting continuation when cleaning fails.
