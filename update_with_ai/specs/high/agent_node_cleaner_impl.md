# agent_node_cleaner_impl implementation component

imports: dag_storage, agent_runner, sandbox, agent_conversation_history, bazel_graph_storage, node_config, model_config
implements: agent_node_cleaner, dag_node_cleaner

## Purpose

The agent_node_cleaner_impl implementation component realizes node clean execution, synthetic startup transcript seeding, and outcome message dispatching for agent-driven nodes.

Driving node execution requires bridging abstract graph clean directives to concrete multi-turn turn loops and translating tool termination responses back into graph messages. The agent_node_cleaner_impl implementation component configures session sandboxes from stored target metadata, injects paired startup executions into conversation histories, executes the agent loop, and converts termination responses into propagating graph updates.

**Out of scope:** The agent_node_cleaner_impl implementation component does not parse JSON build manifests, enforce repetition thresholds, or write transcript logs to disk; these are handled by other components.

## Types and Behavior

The agent node cleaner cleans a dirty node within an agent session phase, establishing the scope where session services operate and configuring the cleaned node with the target node.

Within the agent session phase, cleaning executes the agent runner, the session environment, and the conversation history.

Startup templates provided by the session environment are materialized into missing read-write files before agent interaction.

The conversation history is seeded with startup context comprising the node definition and task prompt retrieved from graph storage for the dirty node, incoming pending messages ordered deterministically by content, and paired startup tool executions from the session environment formatted with synthetic tool requests and captured responses. When seeding the task prompt for a node configured with a guide, the prompt is augmented with instructions directing the agent to call advance without arguments to view each guide step and not supply a change summary until all guide steps are complete when progressive guidance is active, or identifying the guide file by its file alias when progressive guidance is inactive.

Execution of the agent runner resolves the dirty node based on the produced agent outcome.

Resolving the dirty node produces:

- Change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications.

- Feedback messages addressed to an upstream node when the outcome signals blame attributed to that dependency node.

- No propagating messages when the outcome signals run failure, leaving the node dirty and communicating that processing cannot continue.
